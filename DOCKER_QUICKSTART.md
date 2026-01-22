# C++ Graph-RAG MCP Server - Docker Quick Start

This guide shows you how to run the C++ Graph-RAG MCP Server using pre-built Docker images from Docker Hub. No building required!

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start with Docker Compose](#quick-start-with-docker-compose)
- [Quick Start with Podman](#quick-start-with-podman)
- [Manual Docker Run](#manual-docker-run)
- [Configuration](#configuration)
- [Accessing the Server](#accessing-the-server)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Choose **one** of the following:

- **Docker Desktop** (Windows/Mac/Linux)
  - Download from: https://www.docker.com/products/docker-desktop
  - Includes docker-compose

- **Podman** (Linux/Mac/Windows)
  - Download from: https://podman.io/getting-started/installation
  - Install podman-compose: `pip install podman-compose`

## Quick Start with Docker Compose

This is the **recommended** method for most users.

### Step 1: Create Project Directory

```bash
# Create a new directory for your configuration
mkdir cpp-graph-rag-mcp
cd cpp-graph-rag-mcp
```

### Step 2: Download Configuration Files

Create a `docker-compose.yml` file:

```yaml
# C++ Graph-RAG MCP Server - Docker Compose
# Compatible with both Docker and Podman (via podman-compose)

services:
  postgres:
    image: docker.io/pgvector/pgvector:pg18-trixie
    container_name: cpp-rag-postgres
    environment:
      POSTGRES_DB: ${DB_NAME:-cpp_codebase}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql
    ports:
      - "${DB_PORT_EXTERNAL:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres} -d ${DB_NAME:-cpp_codebase}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped
    networks:
      - cpp-rag-network

  mcp-server:
    image: YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
    container_name: cpp-rag-mcp
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-cpp_codebase}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-postgres}
      MONITORED_PATHS: ${MONITORED_PATHS:-}
      EMBEDDING_MODEL: ${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}
      CONFIG_PATH: /app/config
      PYTHONUNBUFFERED: 1
    volumes:
      # Mount your source code (read-only)
      - ${HOST_PATH:-./code}:/host:ro
      # Persistent configuration
      - cpp_rag_config:/app/config
    ports:
      - "${MCP_PORT:-8000}:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    networks:
      - cpp-rag-network

volumes:
  postgres_data:
    driver: local
  cpp_rag_config:
    driver: local

networks:
  cpp-rag-network:
    driver: bridge
```

### Step 3: Create Environment File

Create a `.env` file to customize your setup:

```bash
# Path to your C++ source code
# Windows: HOST_PATH=C:/Projects/MyCppProject
# Linux/Mac: HOST_PATH=/home/user/projects/mycppproject
HOST_PATH=./code

# Port for MCP server and web UI
MCP_PORT=8000

# Database settings (defaults are fine for most users)
DB_NAME=cpp_codebase
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT_EXTERNAL=5432

# Optional: Specify paths to monitor (configure via web UI otherwise)
# MONITORED_PATHS=/host/src,/host/include

# Optional: Use a different embedding model
# EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

### Step 4: Start the Services

**Using Docker:**
```bash
docker-compose up -d
```

**Using Podman:**
```bash
podman-compose up -d
```

### Step 5: Access the Web UI

Open your browser and navigate to:
```
http://localhost:8000
```

You can now configure paths to monitor and start indexing your C++ codebase!

## Quick Start with Podman

If you prefer using Podman without compose:

### Step 1: Create Network
```bash
podman network create cpp-rag-network
```

### Step 2: Create Volumes
```bash
podman volume create postgres_data
podman volume create cpp_rag_config
```

### Step 3: Start PostgreSQL
```bash
podman run -d \
  --name cpp-rag-postgres \
  --network cpp-rag-network \
  -e POSTGRES_DB=cpp_codebase \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -v postgres_data:/var/lib/postgresql \
  -p 5432:5432 \
  docker.io/pgvector/pgvector:pg18-trixie
```

Wait for PostgreSQL to be ready (~10 seconds).

### Step 4: Start MCP Server
```bash
podman run -d \
  --name cpp-rag-mcp \
  --network cpp-rag-network \
  -e DB_HOST=cpp-rag-postgres \
  -e DB_PORT=5432 \
  -e DB_NAME=cpp_codebase \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  -v /path/to/your/cpp/code:/host:ro \
  -v cpp_rag_config:/app/config \
  -p 8000:8000 \
  YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
```

Replace `/path/to/your/cpp/code` with the actual path to your C++ source code.

## Manual Docker Run

For Docker without compose:

### Step 1: Create Network
```bash
docker network create cpp-rag-network
```

### Step 2: Create Volumes
```bash
docker volume create postgres_data
docker volume create cpp_rag_config
```

### Step 3: Start PostgreSQL
```bash
docker run -d \
  --name cpp-rag-postgres \
  --network cpp-rag-network \
  -e POSTGRES_DB=cpp_codebase \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -v postgres_data:/var/lib/postgresql \
  -p 5432:5432 \
  pgvector/pgvector:pg18-trixie
```

### Step 4: Start MCP Server
```bash
docker run -d \
  --name cpp-rag-mcp \
  --network cpp-rag-network \
  -e DB_HOST=cpp-rag-postgres \
  -e DB_PORT=5432 \
  -e DB_NAME=cpp_codebase \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  -v C:/Projects/MyCppProject:/host:ro \
  -v cpp_rag_config:/app/config \
  -p 8000:8000 \
  YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST_PATH` | Path to your C++ source code (host machine) | `./code` |
| `MCP_PORT` | Port for MCP server and web UI | `8000` |
| `DB_NAME` | PostgreSQL database name | `cpp_codebase` |
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `postgres` |
| `DB_PORT_EXTERNAL` | External PostgreSQL port | `5432` |
| `MONITORED_PATHS` | Comma-separated paths to monitor | (empty) |
| `EMBEDDING_MODEL` | Sentence transformer model | `sentence-transformers/all-MiniLM-L6-v2` |

### Volume Mounts

The server requires two volume mounts:

1. **Source Code** (read-only): Your C++ codebase
   - Windows: `C:/Projects/MyCppProject:/host:ro`
   - Linux: `/home/user/projects:/host:ro`

2. **Configuration** (persistent): Server configuration
   - Named volume: `cpp_rag_config:/app/config`

### Configuring Paths via Web UI

1. Open http://localhost:8000
2. Click "Configuration" tab
3. Click "Add Path"
4. Enter path relative to `/host` (e.g., `/host/src` or `/host/include`)
5. Click "Start Indexing"

## Accessing the Server

### Web UI
- URL: http://localhost:8000
- Features: Configuration, indexing status, search interface

### MCP API Endpoints
- Status: http://localhost:8000/api/status
- List Tools: http://localhost:8000/api/tools/list
- Call Tool: http://localhost:8000/api/tools/call

### Database (Optional)
If you need direct database access:
- Host: `localhost`
- Port: `5432`
- Database: `cpp_codebase`
- User: `postgres`
- Password: `postgres`

## Troubleshooting

### Container Won't Start

Check logs:
```bash
# Docker
docker logs cpp-rag-mcp

# Podman
podman logs cpp-rag-mcp
```

### Database Connection Issues

Verify PostgreSQL is healthy:
```bash
# Docker
docker ps
docker logs cpp-rag-postgres

# Podman
podman ps
podman logs cpp-rag-postgres
```

### Can't Access Web UI

1. Check if containers are running:
   ```bash
   docker ps  # or podman ps
   ```

2. Verify port is not in use:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```

3. Try accessing: http://127.0.0.1:8000

### Indexing Not Working

1. Verify volume mount:
   ```bash
   # Docker
   docker exec cpp-rag-mcp ls -la /host
   
   # Podman
   podman exec cpp-rag-mcp ls -la /host
   ```

2. Check that paths are readable:
   - Ensure source code path exists
   - Verify read permissions
   - On Windows with Docker Desktop, ensure drive sharing is enabled

### Reset Everything

Stop and remove containers, volumes:
```bash
# Docker
docker-compose down -v

# Podman
podman-compose down -v

# Or manually:
docker stop cpp-rag-mcp cpp-rag-postgres
docker rm cpp-rag-mcp cpp-rag-postgres
docker volume rm postgres_data cpp_rag_config
```

Then start fresh with Step 4 of Quick Start.

## Performance Tips

1. **Use specific paths**: Instead of mounting entire drives, mount specific project directories
2. **Exclude build artifacts**: Don't index `build/`, `bin/`, `obj/` directories
3. **Adjust resources**: Give Docker/Podman more RAM if indexing large codebases
4. **Use SSD**: Store volumes on SSD for better performance

## Security Notes

1. **Default credentials**: Change default PostgreSQL password in production
2. **Network exposure**: By default, only exposed to localhost
3. **Read-only mounts**: Source code is mounted read-only for safety
4. **Firewall**: Ensure ports 8000 and 5432 are appropriately secured

## Next Steps

- Read the [full documentation](./README.md)
- Learn about [crash analysis features](./docs/CRASH_ANALYSIS_GUIDE.md)
- Configure [Visual Studio 2026 integration](./docs/VS2026_INTEGRATION_GUIDE.md)
- Explore [usage examples](./docs/USAGE_EXAMPLES.md)

## Support

For issues and questions:
- GitHub Issues: [Your Repository URL]
- Documentation: [Your Documentation URL]
