# Getting Started with Docker - 5-Minute Guide

Get the C++ Graph-RAG MCP Server running in 5 minutes using Docker!

## Prerequisites

Install **one** of these:

- **Docker Desktop** (easiest): https://www.docker.com/products/docker-desktop
- **Podman Desktop**: https://podman-desktop.io

## Step 1: Create Directory

Open terminal/PowerShell:

```bash
# Create and enter directory
mkdir cpp-graph-rag
cd cpp-graph-rag
```

## Step 2: Create docker-compose.yml

Create a file named `docker-compose.yml` with this content:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18-trixie
    environment:
      POSTGRES_DB: cpp_codebase
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  mcp-server:
    image: YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: cpp_codebase
      DB_USER: postgres
      DB_PASSWORD: postgres
    volumes:
      # CHANGE THIS: Point to your C++ code
      - C:/Projects/MyCppProject:/host:ro  # Windows
      # - /home/user/projects:/host:ro     # Linux/Mac
      - config:/app/config
    ports:
      - "8000:8000"

volumes:
  postgres_data:
  config:
```

**Important**: Change the volume path to point to your C++ source code!

## Step 3: Start Services

```bash
# Using Docker
docker-compose up -d

# Using Podman
podman-compose up -d
```

Wait ~30 seconds for services to start.

## Step 4: Access Web UI

Open your browser:

```
http://localhost:8000
```

## Step 5: Configure Paths

In the web UI:

1. Click **"Configuration"** tab
2. Click **"Add Path"**
3. Enter path relative to `/host`, example: `/host/src`
4. Click **"Start Indexing"**

Done! Your C++ codebase is now being indexed.

## Using the Server

### Web UI

- **Search**: Semantic search across your codebase
- **Call Graph**: Visualize function dependencies
- **Crash Analysis**: Analyze crash dumps (Windows)
- **Configuration**: Manage monitored paths

### API

Example search:

```bash
curl -X POST http://localhost:8000/api/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_code",
    "arguments": {"query": "database connection"}
  }'
```

### Available MCP Tools

List all tools:

```bash
curl http://localhost:8000/api/tools/list
```

Common tools:
- `search_code` - Semantic code search
- `analyze_call_graph` - Function call analysis
- `get_symbol_definition` - Find symbol definitions
- `analyze_crash_dump` - Crash dump analysis (Windows)

## Managing Services

### View Logs

```bash
# Docker
docker-compose logs -f

# Podman
podman-compose logs -f
```

### Stop Services

```bash
# Docker
docker-compose down

# Podman
podman-compose down
```

### Restart Services

```bash
# Docker
docker-compose restart

# Podman
podman-compose restart
```

## Troubleshooting

### Can't access web UI?

```bash
# Check if running
docker ps
# or
podman ps

# View logs
docker logs cpp-graph-rag-mcp-server-1
# or
podman logs cpp-graph-rag-mcp-server-1
```

### Database connection errors?

```bash
# Check PostgreSQL is running
docker ps | grep postgres
# or
podman ps | grep postgres

# Check health
docker exec cpp-graph-rag-postgres-1 pg_isready -U postgres
# or
podman exec cpp-graph-rag-postgres-1 pg_isready -U postgres
```

### Can't see my source code?

1. Verify path in `docker-compose.yml` is correct
2. Check Docker Desktop has drive sharing enabled (Windows/Mac)
3. Test mount:
   ```bash
   docker exec cpp-graph-rag-mcp-server-1 ls -la /host
   # or
   podman exec cpp-graph-rag-mcp-server-1 ls -la /host
   ```

### Reset everything

```bash
# Docker
docker-compose down -v
docker-compose up -d

# Podman
podman-compose down -v
podman-compose up -d
```

**Note**: This deletes all indexed data!

## Windows-Specific Notes

### Docker Desktop

1. Ensure WSL2 is enabled
2. Enable drive sharing:
   - Settings > Resources > File Sharing
   - Add your drive (C:, D:, etc.)

### Path Format

Use forward slashes in docker-compose.yml:

```yaml
# Good
- C:/Projects/MyApp:/host:ro

# Bad
- C:\Projects\MyApp:/host:ro
```

## Next Steps

### Learn More

- **Full Documentation**: See `DOCKER_QUICKSTART.md`
- **Command Reference**: See `QUICK_REFERENCE.md`
- **Advanced Usage**: See `docs/USAGE_EXAMPLES.md`
- **Crash Analysis**: See `docs/CRASH_ANALYSIS_GUIDE.md`

### Customize

Edit `.env` file for advanced configuration:

```bash
# Download template
# Copy env.production.example to .env

# Edit settings
HOST_PATH=C:/Projects
MCP_PORT=8000
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Then use:

```bash
docker-compose -f docker-compose.production.yml up -d
```

### Production Deployment

For production use:

1. Change default passwords in `docker-compose.yml`
2. Don't expose PostgreSQL externally
3. Use specific version tags instead of `latest`
4. Set up regular backups
5. Monitor logs and health

See `DOCKER_DEPLOYMENT.md` for details.

## Common Use Cases

### 1. Explore Unfamiliar Codebase

```bash
# Search for authentication code
curl -X POST http://localhost:8000/api/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"search_code","arguments":{"query":"user authentication"}}'
```

### 2. Understand Function Calls

```bash
# Analyze call graph for a function
curl -X POST http://localhost:8000/api/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"analyze_call_graph","arguments":{"symbol":"processRequest"}}'
```

### 3. Debug Crash (Windows)

```bash
# Analyze crash dump
curl -X POST http://localhost:8000/api/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"analyze_crash_dump","arguments":{"dump_path":"C:/dumps/app.dmp"}}'
```

## Performance Tips

1. **Index specific directories**: Don't index `build/`, `bin/`, `obj/`
2. **Allocate resources**: Give Docker/Podman 4GB+ RAM for large codebases
3. **Use SSD**: Store volumes on SSD for better performance
4. **Limit scope**: Mount specific project directories, not entire drives

## Support

- **Issues**: Open GitHub issue
- **Questions**: Check documentation in `docs/`
- **Status**: http://localhost:8000/api/status

## Quick Command Reference

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f

# Restart
docker-compose restart

# Status
curl http://localhost:8000/api/status

# Shell access
docker exec -it cpp-graph-rag-mcp-server-1 /bin/bash
```

---

**That's it!** You now have a powerful C++ code analysis server running locally. 🎉

For detailed documentation, see:
- `DOCKER_QUICKSTART.md` - Comprehensive guide
- `QUICK_REFERENCE.md` - All commands
- `README.md` - Full documentation
