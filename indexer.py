"""
Enhanced file indexer that uses tree-sitter parser
Handles incremental updates and relationship resolution
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json

import asyncpg
from sentence_transformers import SentenceTransformer

from parser import parse_cpp_file, Entity, Relationship, CodeChunk


class CodeIndexer:
    """Handles indexing of C++ code files"""
    
    def __init__(self, db_pool: asyncpg.Pool, embedding_model: SentenceTransformer):
        self.db_pool = db_pool
        self.embedding_model = embedding_model
        self.entity_cache: Dict[str, int] = {}  # qualified_name -> entity_id
    
    async def index_file(self, file_path: Path, file_id: int, content: str):
        """Index a single file completely"""
        
        # Parse the file
        try:
            entities, relationships, chunks = parse_cpp_file(file_path, content)
        except Exception as e:
            print(f"Parse error for {file_path}: {e}")
            # Fall back to simple chunking
            await self._simple_file_indexing(file_id, content)
            return
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Delete old entities for this file (cascade will handle chunks and relationships)
                await conn.execute("DELETE FROM entities WHERE file_id = $1", file_id)
                
                # Insert entities
                entity_map = {}  # temporary qualified_name -> db_id mapping
                for entity in entities:
                    entity_id = await self._insert_entity(conn, file_id, entity)
                    entity_map[entity.qualified_name] = entity_id
                    self.entity_cache[entity.qualified_name] = entity_id
                
                # Resolve parent relationships
                for entity in entities:
                    if "::" in entity.qualified_name:
                        # Try to find parent
                        parts = entity.qualified_name.rsplit("::", 1)
                        if len(parts) == 2:
                            parent_name = parts[0]
                            if parent_name in entity_map:
                                await conn.execute(
                                    "UPDATE entities SET parent_id = $1 WHERE id = $2",
                                    entity_map[parent_name],
                                    entity_map[entity.qualified_name]
                                )
                
                # Insert relationships
                for rel in relationships:
                    await self._insert_relationship(conn, rel, entity_map, file_id)
                
                # Insert chunks with embeddings
                for chunk in chunks:
                    await self._insert_chunk(conn, chunk, entity_map, file_id)
                
                # Update file status
                await conn.execute(
                    "UPDATE files SET status = 'indexed', last_indexed = $1 WHERE id = $2",
                    datetime.now(timezone.utc),
                    file_id
                )
        
        print(f"Indexed {file_path}: {len(entities)} entities, {len(relationships)} relationships, {len(chunks)} chunks")
    
    async def _insert_entity(self, conn: asyncpg.Connection, file_id: int, entity: Entity) -> int:
        """Insert an entity and return its ID"""
        entity_id = await conn.fetchval("""
            INSERT INTO entities (
                file_id, type, qualified_name, simple_name, signature,
                start_line, end_line, complexity_score, is_public, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """, file_id, entity.type, entity.qualified_name, entity.simple_name,
            entity.signature, entity.start_line, entity.end_line,
            entity.complexity_score, entity.is_public, json.dumps(entity.metadata))
        
        return entity_id
    
    async def _insert_relationship(self, conn: asyncpg.Connection, rel: Relationship,
                                   entity_map: Dict[str, int], file_id: int):
        """Insert a relationship between entities"""
        
        # Resolve from_entity
        from_id = None
        if rel.from_entity in entity_map:
            from_id = entity_map[rel.from_entity]
        elif rel.from_entity in self.entity_cache:
            from_id = self.entity_cache[rel.from_entity]
        
        # For includes, we don't have a from_entity (file-level)
        if rel.relationship_type == "includes":
            # Just store as metadata for now
            return
        
        # Resolve to_entity
        to_id = None
        if rel.to_entity in entity_map:
            to_id = entity_map[rel.to_entity]
        elif rel.to_entity in self.entity_cache:
            to_id = self.entity_cache[rel.to_entity]
        else:
            # Try to find by simple name (less precise)
            simple_name = rel.to_entity.split("::")[-1]
            to_id = await conn.fetchval(
                "SELECT id FROM entities WHERE simple_name = $1 LIMIT 1",
                simple_name
            )
        
        # Only insert if we could resolve both entities
        if from_id and to_id:
            await conn.execute("""
                INSERT INTO relationships (
                    from_entity_id, to_entity_id, relationship_type, context, line_number
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
            """, from_id, to_id, rel.relationship_type, rel.context, rel.line_number)
    
    async def _insert_chunk(self, conn: asyncpg.Connection, chunk: CodeChunk,
                           entity_map: Dict[str, int], file_id: int):
        """Insert a code chunk with its embedding"""
        
        # Generate embedding
        embedding = self.embedding_model.encode(chunk.content).tolist()
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Resolve entity_id
        entity_id = None
        if chunk.entity_name and chunk.entity_name in entity_map:
            entity_id = entity_map[chunk.entity_name]
        
        await conn.execute("""
            INSERT INTO code_chunks (
                entity_id, file_id, chunk_type, content, start_line, end_line, embedding, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8)
        """, entity_id, file_id, chunk.chunk_type, chunk.content,
            chunk.start_line, chunk.end_line, embedding_str, json.dumps(chunk.metadata))
    
    async def _simple_file_indexing(self, file_id: int, content: str):
        """Fallback: simple chunking when parsing fails"""
        lines = content.splitlines()
        
        # Create overlapping chunks of ~100 lines
        chunk_size = 100
        overlap = 20
        
        async with self.db_pool.acquire() as conn:
            for i in range(0, len(lines), chunk_size - overlap):
                chunk_lines = lines[i:i + chunk_size]
                chunk_text = "\n".join(chunk_lines)
                
                if len(chunk_text.strip()) < 50:  # Skip tiny chunks
                    continue
                
                embedding = self.embedding_model.encode(chunk_text).tolist()
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                await conn.execute("""
                    INSERT INTO code_chunks (
                        file_id, chunk_type, content, start_line, end_line, embedding, metadata
                    ) VALUES ($1, 'mixed', $2, $3, $4, $5::vector, $6)
                """, file_id, chunk_text, i + 1, i + len(chunk_lines),
                    embedding_str, json.dumps({"fallback": True}))


async def batch_index_files(file_paths: List[Path], db_pool: asyncpg.Pool,
                            embedding_model: SentenceTransformer):
    """Index multiple files in parallel"""
    indexer = CodeIndexer(db_pool, embedding_model)
    
    # Process in smaller batches to avoid overwhelming the system
    batch_size = 10
    
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        tasks = []
        
        for file_path in batch:
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"Could not read {file_path}: {e}")
                continue
            
            # Get or create file record
            import hashlib
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            async with db_pool.acquire() as conn:
                file_id = await conn.fetchval("""
                    INSERT INTO files (path, content_hash, last_modified, file_type, loc, status)
                    VALUES ($1, $2, $3, $4, $5, 'indexing')
                    ON CONFLICT (path) DO UPDATE
                    SET content_hash = $2, last_modified = $3, loc = $5, status = 'indexing'
                    RETURNING id
                """, str(file_path), content_hash,
                    datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc),
                    file_path.suffix,
                    len(content.splitlines()))
            
            # Create indexing task
            tasks.append(indexer.index_file(file_path, file_id, content))
        
        # Execute batch and check for exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error indexing {batch[i]}: {result}")
