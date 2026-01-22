"""
C++ Graph-RAG MCP Server
HTTP-based MCP server for analyzing large C++ codebases
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncpg
from sentence_transformers import SentenceTransformer
import numpy as np

# MCP Protocol Models
class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class ListToolsResult(BaseModel):
    tools: List[Tool]

class CallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class CallToolResult(BaseModel):
    content: List[Dict[str, Any]]
    isError: Optional[bool] = False

# Application
app = FastAPI(title="C++ Graph-RAG MCP Server")

# Global state
db_pool: Optional[asyncpg.Pool] = None
embedding_model: Optional[SentenceTransformer] = None
monitoring_paths: List[Path] = []

# Indexing status tracking
indexing_status = {
    "total_files": 0,
    "indexed_files": 0,
    "pending_files": 0,
    "current_file": "",
    "is_indexing": False,
    "last_indexed": None,
    "entities_count": 0,
    "relationships_count": 0,
    "chunks_count": 0
}

# Configuration from environment
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "cpp_codebase")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
MONITORED_PATHS = os.getenv("MONITORED_PATHS", "").split(",")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "/app/config"))

# Mount static files for web UI
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/")
async def root():
    """Serve the web UI dashboard"""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "C++ Graph-RAG MCP Server", "status": "running"}

@app.on_event("startup")
async def startup():
    """Initialize database connection pool and embedding model"""
    global db_pool, embedding_model, monitoring_paths
    
    # Wait for database to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            db_pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=5,
                max_size=20
            )
            break
        except Exception as e:
            if i < max_retries - 1:
                print(f"Database not ready, retrying in 2 seconds... ({i+1}/{max_retries})")
                await asyncio.sleep(2)
            else:
                raise e
    
    # Initialize schema
    await initialize_database()
    
    # Load embedding model (runs on CPU, but fast enough for local use)
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print("Embedding model loaded")
    
    # Load configuration
    from config_manager import ConfigManager
    config_manager = ConfigManager(CONFIG_PATH)
    config = config_manager.load_config()
    
    # Parse monitoring paths from config or environment
    if config.get("monitored_paths"):
        monitoring_paths = [Path(p) for p in config["monitored_paths"] if p]
    else:
        monitoring_paths = [Path(p.strip()) for p in MONITORED_PATHS if p.strip()]
    
    print(f"Monitoring paths: {monitoring_paths}")
    
    # Start file monitor in background
    asyncio.create_task(file_monitor_loop())
    
    # Start initial indexing
    asyncio.create_task(initial_indexing())

@app.on_event("shutdown")
async def shutdown():
    """Cleanup resources"""
    global db_pool
    if db_pool:
        await db_pool.close()

async def initialize_database():
    """Create database schema if not exists"""
    schema_sql = """
    CREATE EXTENSION IF NOT EXISTS vector;
    
    CREATE TABLE IF NOT EXISTS files (
        id SERIAL PRIMARY KEY,
        path TEXT UNIQUE NOT NULL,
        content_hash VARCHAR(64) NOT NULL,
        last_modified TIMESTAMPTZ NOT NULL,
        last_indexed TIMESTAMPTZ,
        file_type VARCHAR(50),
        loc INTEGER,
        status VARCHAR(20) DEFAULT 'pending'
    );
    
    CREATE TABLE IF NOT EXISTS entities (
        id SERIAL PRIMARY KEY,
        file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
        type VARCHAR(50) NOT NULL,
        qualified_name TEXT NOT NULL,
        simple_name TEXT NOT NULL,
        signature TEXT,
        start_line INTEGER,
        end_line INTEGER,
        complexity_score INTEGER,
        is_public BOOLEAN DEFAULT true,
        parent_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
        metadata JSONB
    );
    
    CREATE INDEX IF NOT EXISTS idx_entities_qualified_name ON entities(qualified_name);
    CREATE INDEX IF NOT EXISTS idx_entities_simple_name ON entities(simple_name);
    CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file_id);
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    
    CREATE TABLE IF NOT EXISTS relationships (
        id SERIAL PRIMARY KEY,
        from_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
        to_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
        relationship_type VARCHAR(50) NOT NULL,
        context TEXT,
        line_number INTEGER,
        is_direct BOOLEAN DEFAULT true
    );
    
    CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_entity_id, relationship_type);
    CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_entity_id, relationship_type);
    
    CREATE TABLE IF NOT EXISTS code_chunks (
        id SERIAL PRIMARY KEY,
        entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
        file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
        chunk_type VARCHAR(50),
        content TEXT NOT NULL,
        start_line INTEGER,
        end_line INTEGER,
        embedding vector(384),
        metadata JSONB
    );
    
    CREATE INDEX IF NOT EXISTS idx_chunks_entity ON code_chunks(entity_id);
    CREATE INDEX IF NOT EXISTS idx_chunks_file ON code_chunks(file_id);
    """
    
    async with db_pool.acquire() as conn:
        await conn.execute(schema_sql)
    
    print("Database schema initialized")

# =============================================================================
# Web UI API Endpoints
# =============================================================================

@app.get("/api/status")
async def get_indexing_status():
    """Get current indexing status"""
    global indexing_status
    
    # Update counts from database (but not during active indexing)
    if db_pool and not indexing_status.get("is_indexing", False):
        try:
            async with db_pool.acquire() as conn:
                entities_count = await conn.fetchval("SELECT COUNT(*) FROM entities")
                relationships_count = await conn.fetchval("SELECT COUNT(*) FROM relationships")
                chunks_count = await conn.fetchval("SELECT COUNT(*) FROM code_chunks")
                total_files = await conn.fetchval("SELECT COUNT(*) FROM files")
                files_indexed = await conn.fetchval("SELECT COUNT(*) FROM files WHERE status = 'indexed'")
                files_pending = await conn.fetchval("SELECT COUNT(*) FROM files WHERE status = 'pending'")
                
                indexing_status["entities_count"] = entities_count or 0
                indexing_status["relationships_count"] = relationships_count or 0
                indexing_status["chunks_count"] = chunks_count or 0
                indexing_status["total_files"] = total_files or 0
                indexing_status["indexed_files"] = files_indexed or 0
                indexing_status["pending_files"] = files_pending or 0
        except Exception as e:
            print(f"Error fetching status: {e}")
    
    return indexing_status

@app.get("/api/directories")
async def get_monitored_directories():
    """Get list of monitored directories"""
    from config_manager import ConfigManager
    config_manager = ConfigManager(CONFIG_PATH)
    config = config_manager.load_config()
    return {
        "monitored_paths": config.get("monitored_paths", []),
        "base_path": str(config.get("base_path", "/host"))
    }

@app.post("/api/directories")
async def update_monitored_directories(request: Dict[str, Any]):
    """Update monitored directories"""
    global monitoring_paths
    
    from config_manager import ConfigManager
    config_manager = ConfigManager(CONFIG_PATH)
    
    paths = request.get("monitored_paths", [])
    config_manager.save_config({"monitored_paths": paths})
    
    # Update in-memory paths
    monitoring_paths = [Path(p) for p in paths if p]
    
    # Trigger re-indexing
    asyncio.create_task(initial_indexing())
    
    return {"status": "ok", "monitored_paths": paths}

@app.delete("/api/directories/{path:path}")
async def delete_directory_data(path: str):
    """Delete all data associated with a directory"""
    try:
        async with db_pool.acquire() as conn:
            # First count the files
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM files 
                WHERE path LIKE $1 || '%'
            """, path)
            
            # Delete files and their cascading data (entities, chunks, relationships)
            await conn.execute("""
                DELETE FROM files 
                WHERE path LIKE $1 || '%'
            """, path)
            
            print(f"Deleted {count} files from path: {path}")
            return {"status": "ok", "deleted_files": count or 0}
    except Exception as e:
        print(f"Error deleting directory data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/browse")
async def browse_directory(path: str = "/host"):
    """Browse directory structure for file picker"""
    try:
        target = Path(path)
        if not target.exists():
            return {"error": f"Path does not exist: {path}", "items": []}
        
        if not target.is_dir():
            return {"error": f"Path is not a directory: {path}", "items": []}
        
        items = []
        try:
            for item in sorted(target.iterdir()):
                # Skip hidden files and common non-code directories
                if item.name.startswith('.'):
                    continue
                if item.name in ['node_modules', '__pycache__', '.git', 'venv', 'env']:
                    continue
                
                item_info = {
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir()
                }
                
                # For directories, count C++ files
                if item.is_dir():
                    try:
                        cpp_count = sum(1 for _ in item.rglob("*.cpp")) + \
                                   sum(1 for _ in item.rglob("*.h")) + \
                                   sum(1 for _ in item.rglob("*.hpp"))
                        item_info["cpp_files"] = min(cpp_count, 9999)  # Cap for performance
                    except:
                        item_info["cpp_files"] = 0
                
                items.append(item_info)
        except PermissionError:
            return {"error": f"Permission denied: {path}", "items": []}
        
        return {
            "current_path": str(target),
            "parent_path": str(target.parent) if target.parent != target else None,
            "items": items
        }
    except Exception as e:
        return {"error": str(e), "items": []}

@app.post("/api/search")
async def quick_search(request: Dict[str, Any]):
    """Quick search endpoint for web UI"""
    query = request.get("query", "")
    max_results = request.get("max_results", 5)
    
    if not query:
        return {"results": []}
    
    result = await search_code(query, max_results, "all")
    return result

@app.post("/api/reindex")
async def trigger_reindex():
    """Manually trigger re-indexing"""
    asyncio.create_task(initial_indexing())
    return {"status": "indexing_started"}

# =============================================================================
# MCP Endpoints
# =============================================================================

@app.get("/mcp/v1/tools")
async def list_tools() -> ListToolsResult:
    """List available MCP tools"""
    tools = [
        Tool(
            name="search_code",
            description="Semantic search across the C++ codebase. Use this to find code patterns, similar implementations, or concepts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of what to find (e.g., 'database connection loops', 'error handling patterns', 'mutex implementations')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["all", "functions", "classes", "files"],
                        "description": "Limit search to specific code element types",
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_symbol",
            description="Find definition and usages of a specific symbol (class, function, variable). Use for precise lookups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name (can be qualified like 'MyNamespace::MyClass::method' or simple like 'method')"
                    },
                    "include_usages": {
                        "type": "boolean",
                        "description": "Include all places where this symbol is used",
                        "default": True
                    },
                    "max_usages": {
                        "type": "integer",
                        "description": "Maximum number of usage examples to return",
                        "default": 20
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="trace_dependencies",
            description="Get dependency graph for a symbol or file. Shows what calls/includes/inherits from what.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Symbol or file path to trace dependencies for"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["incoming", "outgoing", "both"],
                        "description": "Direction of dependencies to trace",
                        "default": "both"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How many levels deep to traverse (1-5)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 5
                    },
                    "relationship_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by relationship types: calls, inherits, includes, uses",
                        "default": ["calls", "inherits", "includes"]
                    }
                },
                "required": ["target"]
            }
        ),
        Tool(
            name="get_context",
            description="Get comprehensive context about a component/module/subsystem for agent work. Returns related code organized by relevance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component name, namespace, or module identifier"
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["brief", "detailed", "comprehensive"],
                        "description": "How much context to gather",
                        "default": "detailed"
                    },
                    "include_related": {
                        "type": "boolean",
                        "description": "Include semantically related code from other modules",
                        "default": True
                    }
                },
                "required": ["component"]
            }
        ),
        Tool(
            name="analyze_debugging_context",
            description="Analyze Visual Studio debugging context to find crash root cause. Use when you've loaded crash dump in VS, navigated to crash location, and want LLM to analyze the execution path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "current_file": {
                        "type": "string",
                        "description": "Full file path where debugger stopped (from VS status bar or call stack)"
                    },
                    "current_line": {
                        "type": "integer",
                        "description": "Line number where debugger stopped"
                    },
                    "exception_info": {
                        "type": "string",
                        "description": "Exception/crash details from VS (e.g., 'Access Violation reading 0x00000000', register values, etc.)"
                    },
                    "call_stack": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Call stack from VS Call Stack window (copy entire stack with symbols loaded)"
                    },
                    "log_file_content": {
                        "type": "string",
                        "description": "Content of application log file (optional but recommended)",
                        "default": ""
                    }
                },
                "required": ["current_file", "current_line", "exception_info", "call_stack"]
            }
        ),
        Tool(
            name="find_code_location",
            description="Find code at a specific file and line number. Use when you have a file path and line number from a crash dump or debugger.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path (can be partial, e.g., 'database_connection.cpp')"
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "Line number in the file"
                    }
                },
                "required": ["file_path", "line_number"]
            }
        ),
        Tool(
            name="explain_code",
            description="Get detailed explanation of a specific code entity with full context. Returns the code plus analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity identifier (qualified name, file path, or natural language description)"
                    },
                    "include_callers": {
                        "type": "boolean",
                        "description": "Include information about what calls this code",
                        "default": True
                    },
                    "include_callees": {
                        "type": "boolean",
                        "description": "Include information about what this code calls",
                        "default": True
                    }
                },
                "required": ["entity"]
            }
        )
    ]
    
    return ListToolsResult(tools=tools)

@app.post("/mcp/v1/tools/call")
async def call_tool(request: CallToolRequest) -> CallToolResult:
    """Execute an MCP tool"""
    try:
        if request.name == "search_code":
            result = await search_code(
                query=request.arguments["query"],
                max_results=request.arguments.get("max_results", 10),
                scope=request.arguments.get("scope", "all")
            )
        elif request.name == "find_symbol":
            result = await find_symbol(
                symbol=request.arguments["symbol"],
                include_usages=request.arguments.get("include_usages", True),
                max_usages=request.arguments.get("max_usages", 20)
            )
        elif request.name == "trace_dependencies":
            result = await trace_dependencies(
                target=request.arguments["target"],
                direction=request.arguments.get("direction", "both"),
                depth=request.arguments.get("depth", 2),
                relationship_types=request.arguments.get("relationship_types", ["calls", "inherits", "includes"])
            )
        elif request.name == "get_context":
            result = await get_context(
                component=request.arguments["component"],
                detail_level=request.arguments.get("detail_level", "detailed"),
                include_related=request.arguments.get("include_related", True)
            )
        elif request.name == "analyze_debugging_context":
            result = await analyze_debugging_context_tool(
                current_file=request.arguments["current_file"],
                current_line=request.arguments["current_line"],
                exception_info=request.arguments["exception_info"],
                call_stack=request.arguments["call_stack"],
                log_file_content=request.arguments.get("log_file_content", "")
            )
        elif request.name == "find_code_location":
            result = await find_code_location_tool(
                file_path=request.arguments["file_path"],
                line_number=request.arguments["line_number"]
            )
        elif request.name == "explain_code":
            result = await explain_code(
                entity=request.arguments["entity"],
                include_callers=request.arguments.get("include_callers", True),
                include_callees=request.arguments.get("include_callees", True)
            )
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{request.name}' not found")
        
        return CallToolResult(content=[{"type": "text", "text": json.dumps(result, indent=2)}])
    
    except Exception as e:
        return CallToolResult(
            content=[{"type": "text", "text": f"Error executing tool: {str(e)}"}],
            isError=True
        )

# =============================================================================
# Tool Implementations
# =============================================================================

async def search_code(query: str, max_results: int, scope: str) -> Dict[str, Any]:
    """Semantic search implementation"""
    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()
    query_embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    # Build scope filter
    scope_filter = ""
    if scope == "functions":
        scope_filter = "AND e.type = 'function'"
    elif scope == "classes":
        scope_filter = "AND e.type IN ('class', 'struct')"
    elif scope == "files":
        scope_filter = "AND c.entity_id IS NULL"  # File-level chunks
    
    # Search using cosine similarity
    sql = f"""
        SELECT 
            c.id,
            c.content,
            c.start_line,
            c.end_line,
            c.chunk_type,
            c.metadata,
            f.path as file_path,
            e.qualified_name,
            e.type as entity_type,
            1 - (c.embedding <=> $1::vector) as similarity
        FROM code_chunks c
        JOIN files f ON c.file_id = f.id
        LEFT JOIN entities e ON c.entity_id = e.id
        WHERE c.embedding IS NOT NULL
        {scope_filter}
        ORDER BY c.embedding <=> $1::vector
        LIMIT $2
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(sql, query_embedding_str, max_results)
    
    results = []
    for row in rows:
        results.append({
            "file": row["file_path"],
            "entity": row["qualified_name"],
            "type": row["entity_type"],
            "content": row["content"],
            "lines": f"{row['start_line']}-{row['end_line']}" if row["start_line"] else "N/A",
            "similarity": float(row["similarity"]),
            "chunk_type": row["chunk_type"]
        })
    
    return {
        "query": query,
        "results_found": len(results),
        "results": results
    }

async def find_symbol(symbol: str, include_usages: bool, max_usages: int) -> Dict[str, Any]:
    """Find symbol definition and usages"""
    # Find the entity
    sql = """
        SELECT 
            e.id,
            e.type,
            e.qualified_name,
            e.signature,
            e.start_line,
            e.end_line,
            f.path as file_path,
            e.complexity_score,
            e.metadata
        FROM entities e
        JOIN files f ON e.file_id = f.id
        WHERE e.qualified_name LIKE $1 OR e.simple_name = $2
        LIMIT 10
    """
    
    async with db_pool.acquire() as conn:
        entities = await conn.fetch(sql, f"%{symbol}%", symbol)
        
        if not entities:
            return {"error": f"Symbol '{symbol}' not found"}
        
        # Get the primary match (best match by qualified name)
        entity = entities[0]
        entity_id = entity["id"]
        
        result = {
            "symbol": entity["qualified_name"],
            "type": entity["type"],
            "signature": entity["signature"],
            "file": entity["file_path"],
            "lines": f"{entity['start_line']}-{entity['end_line']}",
            "complexity": entity["complexity_score"]
        }
        
        # Get the code
        code_sql = """
            SELECT content
            FROM code_chunks
            WHERE entity_id = $1
            ORDER BY start_line
            LIMIT 1
        """
        code_row = await conn.fetchrow(code_sql, entity_id)
        if code_row:
            result["code"] = code_row["content"]
        
        if include_usages:
            # Find incoming relationships (who uses this)
            usages_sql = """
                SELECT 
                    e.qualified_name as caller,
                    e.type as caller_type,
                    f.path as file_path,
                    r.relationship_type,
                    r.context,
                    r.line_number
                FROM relationships r
                JOIN entities e ON r.from_entity_id = e.id
                JOIN files f ON e.file_id = f.id
                WHERE r.to_entity_id = $1
                ORDER BY f.path, r.line_number
                LIMIT $2
            """
            usage_rows = await conn.fetch(usages_sql, entity_id, max_usages)
            
            result["usages"] = [
                {
                    "caller": row["caller"],
                    "type": row["caller_type"],
                    "file": row["file_path"],
                    "line": row["line_number"],
                    "relationship": row["relationship_type"],
                    "context": row["context"]
                }
                for row in usage_rows
            ]
            result["total_usages"] = len(usage_rows)
        
        # If multiple matches found, list them
        if len(entities) > 1:
            result["other_matches"] = [
                {"name": e["qualified_name"], "file": e["file_path"]}
                for e in entities[1:]
            ]
        
        return result

async def trace_dependencies(target: str, direction: str, depth: int, relationship_types: List[str]) -> Dict[str, Any]:
    """Trace dependency graph"""
    async with db_pool.acquire() as conn:
        # Find the target entity
        entity = await conn.fetchrow("""
            SELECT id, qualified_name, type, file_id
            FROM entities
            WHERE qualified_name LIKE $1 OR simple_name = $2
            LIMIT 1
        """, f"%{target}%", target)
        
        if not entity:
            return {"error": f"Target '{target}' not found"}
        
        result = {
            "target": entity["qualified_name"],
            "type": entity["type"],
            "incoming": [],
            "outgoing": []
        }
        
        # Get outgoing dependencies (what this calls/uses)
        if direction in ["outgoing", "both"]:
            outgoing = await conn.fetch("""
                SELECT DISTINCT
                    e.qualified_name,
                    e.type,
                    r.relationship_type,
                    f.path as file_path
                FROM relationships r
                JOIN entities e ON r.to_entity_id = e.id
                JOIN files f ON e.file_id = f.id
                WHERE r.from_entity_id = $1
                AND r.relationship_type = ANY($2)
                LIMIT 50
            """, entity["id"], relationship_types)
            
            result["outgoing"] = [
                {
                    "name": row["qualified_name"],
                    "type": row["type"],
                    "relationship": row["relationship_type"],
                    "file": row["file_path"]
                }
                for row in outgoing
            ]
        
        # Get incoming dependencies (what calls/uses this)
        if direction in ["incoming", "both"]:
            incoming = await conn.fetch("""
                SELECT DISTINCT
                    e.qualified_name,
                    e.type,
                    r.relationship_type,
                    f.path as file_path
                FROM relationships r
                JOIN entities e ON r.from_entity_id = e.id
                JOIN files f ON e.file_id = f.id
                WHERE r.to_entity_id = $1
                AND r.relationship_type = ANY($2)
                LIMIT 50
            """, entity["id"], relationship_types)
            
            result["incoming"] = [
                {
                    "name": row["qualified_name"],
                    "type": row["type"],
                    "relationship": row["relationship_type"],
                    "file": row["file_path"]
                }
                for row in incoming
            ]
        
        return result

async def get_context(component: str, detail_level: str, include_related: bool) -> Dict[str, Any]:
    """Get comprehensive context about a component"""
    async with db_pool.acquire() as conn:
        # Find entities matching the component
        entities = await conn.fetch("""
            SELECT 
                e.id, e.qualified_name, e.type, e.signature,
                e.start_line, e.end_line, f.path as file_path
            FROM entities e
            JOIN files f ON e.file_id = f.id
            WHERE e.qualified_name ILIKE $1
            ORDER BY e.type, e.qualified_name
            LIMIT 20
        """, f"%{component}%")
        
        if not entities:
            return {"error": f"Component '{component}' not found"}
        
        result = {
            "component": component,
            "entities": [],
            "related_code": []
        }
        
        for entity in entities:
            entity_info = {
                "name": entity["qualified_name"],
                "type": entity["type"],
                "signature": entity["signature"],
                "file": entity["file_path"],
                "lines": f"{entity['start_line']}-{entity['end_line']}"
            }
            
            if detail_level in ["detailed", "comprehensive"]:
                # Get code
                code = await conn.fetchval("""
                    SELECT content FROM code_chunks
                    WHERE entity_id = $1
                    LIMIT 1
                """, entity["id"])
                if code:
                    entity_info["code"] = code
            
            result["entities"].append(entity_info)
        
        # Get related code via semantic search
        if include_related:
            query_embedding = embedding_model.encode(component).tolist()
            related = await conn.fetch("""
                SELECT 
                    c.content,
                    f.path as file_path,
                    e.qualified_name,
                    1 - (c.embedding <=> $1::vector) as similarity
                FROM code_chunks c
                JOIN files f ON c.file_id = f.id
                LEFT JOIN entities e ON c.entity_id = e.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT 5
            """, query_embedding)
            
            result["related_code"] = [
                {
                    "name": row["qualified_name"],
                    "file": row["file_path"],
                    "similarity": float(row["similarity"]),
                    "snippet": row["content"][:500]
                }
                for row in related
            ]
        
        return result

async def analyze_debugging_context_tool(
    current_file: str,
    current_line: int,
    exception_info: str,
    call_stack: List[str],
    log_file_content: str
) -> Dict[str, Any]:
    """Analyze Visual Studio debugging context for root cause"""
    from vs_context_analyzer import analyze_vs_debug_context
    
    result = await analyze_vs_debug_context(
        current_file=current_file,
        current_line=current_line,
        exception_info=exception_info,
        call_stack=call_stack,
        log_content=log_file_content if log_file_content else None,
        db_pool=db_pool,
        embedding_model=embedding_model
    )
    
    # Format response for better readability
    response = {
        "summary": f"Analyzed crash at {current_file}:{current_line}",
        "crash_location": result.get("crash_location", {}),
        "execution_path_analysis": {
            "total_frames": len(result.get("execution_path", [])),
            "frames_with_code": [
                {
                    "function": frame["entity"],
                    "file": frame["file"],
                    "lines": frame["lines"],
                    "code_snippet": frame["code"][:500] if frame.get("code") else "Not found in codebase"
                }
                for frame in result.get("execution_path", [])
            ]
        },
        "root_cause_hypotheses": result.get("root_cause_hypothesis", []),
        "log_insights": {},
        "similar_crashes": result.get("similar_patterns", [])
    }
    
    # Add log analysis if available
    if result.get("log_analysis"):
        log_analysis = result["log_analysis"]
        response["log_insights"] = {
            "errors_before_crash": log_analysis.get("errors_before_crash", [])[-5:],  # Last 5
            "warnings_before_crash": log_analysis.get("warnings_before_crash", [])[-5:],  # Last 5
            "relevant_log_entries": log_analysis.get("relevant_entries", [])[-10:],  # Last 10
            "state_variables": log_analysis.get("state_info", {})
        }
    
    # Generate analysis summary
    response["analysis_summary"] = _generate_analysis_summary(response)
    
    return response

def _generate_analysis_summary(analysis: Dict) -> str:
    """Generate human-readable summary"""
    parts = []
    
    # Crash location
    crash_loc = analysis.get("crash_location", {})
    if crash_loc:
        parts.append(
            f"Crash occurred in {crash_loc.get('entity', 'unknown')} "
            f"at {crash_loc.get('file')}:{crash_loc.get('line')}"
        )
        parts.append(f"Exception: {crash_loc.get('exception')}")
    
    # Execution path
    exec_path = analysis.get("execution_path_analysis", {})
    if exec_path.get("total_frames"):
        parts.append(
            f"Found code for {len(exec_path.get('frames_with_code', []))} "
            f"out of {exec_path['total_frames']} stack frames in your codebase"
        )
    
    # Root cause hypotheses
    hypotheses = analysis.get("root_cause_hypotheses", [])
    if hypotheses:
        high_priority = [h for h in hypotheses if h.get("priority") == "HIGH" or h.get("priority") == "CRITICAL"]
        if high_priority:
            parts.append(f"Top hypothesis: {high_priority[0]['hypothesis']}")
    
    # Log insights
    log_insights = analysis.get("log_insights", {})
    if log_insights.get("errors_before_crash"):
        parts.append(f"Found {len(log_insights['errors_before_crash'])} errors in log before crash")
    
    return ". ".join(parts) + "."

async def find_code_location_tool(file_path: str, line_number: int) -> Dict[str, Any]:
    """Find code at specific location"""
    from crash_analyzer import find_code_at_location
    
    result = await find_code_at_location(file_path, line_number, db_pool)
    
    if not result:
        return {
            "error": f"No code found at {file_path}:{line_number}",
            "suggestion": "Check if the file path is correct and if the code has been indexed"
        }
    
    return {
        "location": f"{result['file_path']}:{line_number}",
        "entity": {
            "name": result['qualified_name'],
            "type": result['type'],
            "signature": result['signature'],
            "full_range": f"lines {result['start_line']}-{result['end_line']}"
        },
        "code": result['code'],
        "context": f"This location is inside {result['type']} '{result['qualified_name']}'"
    }

async def explain_code(entity: str, include_callers: bool, include_callees: bool) -> Dict[str, Any]:
    """Get detailed code explanation"""
    async with db_pool.acquire() as conn:
        # Find the entity
        entity_row = await conn.fetchrow("""
            SELECT 
                e.id, e.qualified_name, e.type, e.signature,
                e.start_line, e.end_line, e.complexity_score,
                f.path as file_path
            FROM entities e
            JOIN files f ON e.file_id = f.id
            WHERE e.qualified_name LIKE $1 OR e.simple_name = $2
            LIMIT 1
        """, f"%{entity}%", entity)
        
        if not entity_row:
            return {"error": f"Entity '{entity}' not found"}
        
        result = {
            "entity": entity_row["qualified_name"],
            "type": entity_row["type"],
            "signature": entity_row["signature"],
            "file": entity_row["file_path"],
            "lines": f"{entity_row['start_line']}-{entity_row['end_line']}",
            "complexity": entity_row["complexity_score"]
        }
        
        # Get the code
        code = await conn.fetchval("""
            SELECT content FROM code_chunks
            WHERE entity_id = $1
            LIMIT 1
        """, entity_row["id"])
        
        if code:
            result["code"] = code
        
        # Get callers
        if include_callers:
            callers = await conn.fetch("""
                SELECT DISTINCT e.qualified_name, e.type, f.path
                FROM relationships r
                JOIN entities e ON r.from_entity_id = e.id
                JOIN files f ON e.file_id = f.id
                WHERE r.to_entity_id = $1 AND r.relationship_type = 'calls'
                LIMIT 20
            """, entity_row["id"])
            result["callers"] = [
                {"name": c["qualified_name"], "type": c["type"], "file": c["path"]}
                for c in callers
            ]
        
        # Get callees
        if include_callees:
            callees = await conn.fetch("""
                SELECT DISTINCT e.qualified_name, e.type, f.path
                FROM relationships r
                JOIN entities e ON r.to_entity_id = e.id
                JOIN files f ON e.file_id = f.id
                WHERE r.from_entity_id = $1 AND r.relationship_type = 'calls'
                LIMIT 20
            """, entity_row["id"])
            result["callees"] = [
                {"name": c["qualified_name"], "type": c["type"], "file": c["path"]}
                for c in callees
            ]
        
        return result

# =============================================================================
# File Monitoring and Indexing
# =============================================================================

async def file_monitor_loop():
    """Monitor directories for changes every 30 seconds"""
    await asyncio.sleep(5)  # Wait for initial indexing to start
    
    while True:
        try:
            await asyncio.sleep(30)
            print("Checking for file changes...")
            await check_for_changes()
        except Exception as e:
            print(f"Error in file monitor: {e}")

async def check_for_changes():
    """Check monitored directories for changes"""
    changed_files = []
    
    for base_path in monitoring_paths:
        if not base_path.exists():
            continue
        
        # Find all C++ files
        for ext in ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.h", "*.hxx"]:
            for file_path in base_path.rglob(ext):
                if file_path.is_file():
                    # Calculate file hash
                    content_hash = calculate_file_hash(file_path)
                    
                    # Check if file exists in DB and if hash changed
                    async with db_pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT id, content_hash FROM files WHERE path = $1",
                            str(file_path)
                        )
                        
                        if not row:
                            # New file
                            changed_files.append(file_path)
                        elif row["content_hash"] != content_hash:
                            # Modified file
                            changed_files.append(file_path)
    
    if changed_files:
        print(f"Found {len(changed_files)} changed files, starting incremental indexing...")
        await index_files(changed_files)
    else:
        print("No changes detected")

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

async def initial_indexing():
    """Initial indexing of all files"""
    global indexing_status
    
    print("Starting initial indexing...")
    indexing_status["is_indexing"] = True
    await asyncio.sleep(1)  # Let server start up
    
    all_files = []
    for base_path in monitoring_paths:
        if not base_path.exists():
            print(f"Warning: Path does not exist: {base_path}")
            continue
        
        for ext in ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.h", "*.hxx"]:
            all_files.extend(base_path.rglob(ext))
    
    indexing_status["total_files"] = len(all_files)
    print(f"Found {len(all_files)} C++ files to index")
    
    # Index in batches
    batch_size = 50
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i+batch_size]
        indexing_status["current_file"] = str(batch[0]) if batch else ""
        await index_files(batch)
        indexing_status["indexed_files"] = min(i+batch_size, len(all_files))
        print(f"Indexed {min(i+batch_size, len(all_files))}/{len(all_files)} files")
    
    indexing_status["is_indexing"] = False
    indexing_status["last_indexed"] = datetime.now(timezone.utc).isoformat()
    indexing_status["current_file"] = ""

async def index_files(file_paths: List[Path]):
    """Index a batch of files using the enhanced indexer"""
    from indexer import batch_index_files
    await batch_index_files(file_paths, db_pool, embedding_model)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
