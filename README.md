# C++ Graph-RAG MCP Server

A powerful Model Context Protocol (MCP) server for analyzing large C++ codebases using Graph-RAG architecture. Features semantic search, crash dump analysis, and a web UI for configuration.

## Features

- **Graph-RAG Architecture**: Combines semantic search (RAG) with relationship graphs
- **Crash Dump Analysis**: Parse stack traces and find problematic code instantly
- **Tree-sitter Parsing**: Accurate C++ parsing that understands syntax
- **Incremental Indexing**: Smart change detection and efficient updates
- **pgvector Storage**: Fast vector similarity search
- **Web UI Dashboard**: Configure directories and monitor indexing status
- **Docker + Podman**: Works with both container runtimes

## Quick Start

### Prerequisites

- Docker (20.x+) or Podman (4.x+)
- 4GB+ RAM (8GB recommended for large codebases)
- 5GB free disk space

### 1. Configure Environment

```bash
# Copy example config
cp env.example .env

# Edit .env to set your source code path
# Windows example: HOST_PATH=C:/Projects
# Linux example: HOST_PATH=/home/user/projects
```

### 2. Build and Start

**Using Docker:**
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server
```

**Using Podman:**
```bash
# Build images
podman-compose build

# Start services
podman-compose up -d

# View logs
podman-compose logs -f mcp-server
```

### 3. Configure Directories

Open the web UI at **http://localhost:8000** to:

1. Browse your mounted directories
2. Select folders to index
3. Monitor indexing progress
4. Test searches

### 4. Connect to Claude Desktop / VS Code

Add to your MCP client configuration:

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):
```json
{
  "mcpServers": {
    "cpp-codebase": {
      "url": "http://localhost:8000/mcp/v1"
    }
  }
}
```

**VS Code** (MCP extension settings):
```json
{
  "mcp.servers": {
    "cpp-codebase": "http://localhost:8000/mcp/v1"
  }
}
```

## Web UI

The dashboard at `http://localhost:8000` provides:

| Feature | Description |
|---------|-------------|
| **Indexing Status** | View files indexed, entities found, progress |
| **Directory Browser** | Navigate and select directories to index |
| **Quick Search** | Test semantic search queries |
| **Re-index Button** | Manually trigger re-indexing |

## Available MCP Tools

### search_code
Semantic search across your codebase.

```
"Find database connection patterns"
"Show mutex locking implementations"
```

### find_symbol
Precise symbol lookup with usages.

```
"Find ConnectionPool::acquire"
"Where is DatabaseManager defined?"
```

### trace_dependencies
Graph traversal for dependencies.

```
"What does AuthManager depend on?"
"Show me everything that calls validateUser"
```

### get_context
Comprehensive context for AI agents.

```
"Get context about the payment processing module"
```

### analyze_debugging_context
Analyze crash dumps from Visual Studio.

```
Provide: file path, line number, exception info, call stack
```

### find_code_location
Navigate to specific file and line.

```
"Show me database_connection.cpp line 95"
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_PATH` | `./example_code` | Path to mount as `/host` |
| `MONITORED_PATHS` | (empty) | Comma-separated paths to index |
| `MCP_PORT` | `8000` | Port for API and web UI |
| `DB_NAME` | `cpp_codebase` | PostgreSQL database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |

### Volume Mounting

Mount your source code as read-only:

```yaml
volumes:
  # Mount entire drive (Windows)
  - C:/:/host:ro
  
  # Mount specific directory (Linux)
  - /home/user/projects:/host:ro
```

Then use the web UI to select specific subdirectories.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Container Network                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  PostgreSQL 18      │    │  MCP Server                 │ │
│  │  + pgvector         │◄───│  + FastAPI                  │ │
│  │  (pg18-trixie)      │    │  + Web UI                   │ │
│  │  Port: 5432         │    │  Port: 8000                 │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Commands Reference

### Docker

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f mcp-server

# Rebuild after code changes
docker-compose build --no-cache

# Reset database (deletes all indexed data)
docker-compose down -v
docker-compose up -d

# Check status
docker-compose ps

# Enter container shell
docker-compose exec mcp-server bash
```

### Podman

```bash
# Start
podman-compose up -d

# Stop
podman-compose down

# View logs
podman-compose logs -f mcp-server

# Rebuild
podman-compose build --no-cache

# Reset database
podman-compose down -v
podman-compose up -d
```

### API Endpoints

```bash
# Check health
curl http://localhost:8000/api/status

# List MCP tools
curl http://localhost:8000/mcp/v1/tools

# Search code
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection"}'

# Get directories
curl http://localhost:8000/api/directories

# Browse directory
curl "http://localhost:8000/api/browse?path=/host"
```

## Troubleshooting

### Server won't start

```bash
# Check logs
docker-compose logs mcp-server

# Common issues:
# - PostgreSQL not ready: Wait 30 seconds
# - Port in use: Change MCP_PORT in .env
# - Out of memory: Increase Docker memory limit
```

### No files indexed

```bash
# Verify mount
docker-compose exec mcp-server ls -la /host

# Check configured paths
curl http://localhost:8000/api/directories
```

### Slow indexing

```bash
# Use faster embedding model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Check database size
docker-compose exec postgres psql -U postgres -d cpp_codebase \
  -c "SELECT pg_size_pretty(pg_database_size('cpp_codebase'));"
```

### Permission denied on Linux

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Or use podman (rootless by default)
podman-compose up -d
```

## Performance Tips

| Codebase Size | RAM | First Index Time |
|---------------|-----|------------------|
| 10K LOC | 4GB | ~30 seconds |
| 100K LOC | 4GB | ~5 minutes |
| 1M LOC | 8GB | ~45 minutes |
| 3M+ LOC | 16GB | ~2 hours |

### For Large Codebases

1. Start with a single module to test
2. Use the fast embedding model (default)
3. Index only needed directories via web UI
4. Consider SSD for database volume

## Project Structure

```
cpp-graph-rag-mcp/
├── server.py              # Main MCP server (FastAPI)
├── parser.py              # Tree-sitter C++ parser
├── indexer.py             # Code indexer
├── crash_analyzer.py      # Crash dump analysis
├── vs_context_analyzer.py # VS debugging integration
├── config_manager.py      # Configuration persistence
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container build
├── docker-compose.yml     # Multi-container setup
├── env.example            # Configuration template
├── static/                # Web UI files
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── example_code/          # Sample C++ for testing
└── docs/                  # Documentation
```

## Security Notes

- Server runs on localhost only by default
- Code is mounted read-only
- Database password should be changed for production
- No data leaves your machine (local embeddings)

## License

MIT License - Free to use and modify.

## Contributing

Key areas for improvement:
- Template specialization handling
- Macro expansion tracking
- Multi-language support
- Visual dependency graph viewer
