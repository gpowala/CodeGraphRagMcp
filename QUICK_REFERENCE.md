# C++ Graph-RAG MCP Server - Quick Reference

Quick commands and common operations for Docker/Podman deployments.

## Table of Contents

- [Installation](#installation)
- [Starting & Stopping](#starting--stopping)
- [Monitoring](#monitoring)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Installation

### Pull Pre-built Image

**Docker:**
```bash
docker pull YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
```

**Podman:**
```bash
podman pull YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
```

### Quick Start with Compose

```bash
# Download docker-compose.production.yml and .env.production
# Customize .env.production and rename to .env
# Then start:

# Docker
docker-compose -f docker-compose.production.yml up -d

# Podman
podman-compose -f docker-compose.production.yml up -d
```

---

## Starting & Stopping

### Docker Compose

```bash
# Start (in background)
docker-compose up -d

# Start (with logs)
docker-compose up

# Stop
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v

# Restart
docker-compose restart

# Restart specific service
docker-compose restart mcp-server
```

### Podman Compose

```bash
# Start (in background)
podman-compose up -d

# Start (with logs)
podman-compose up

# Stop
podman-compose down

# Stop and remove volumes (⚠️ deletes data)
podman-compose down -v

# Restart
podman-compose restart

# Restart specific service
podman-compose restart mcp-server
```

### Manual Container Management

**Docker:**
```bash
# Start
docker start cpp-rag-mcp cpp-rag-postgres

# Stop
docker stop cpp-rag-mcp cpp-rag-postgres

# Restart
docker restart cpp-rag-mcp

# Remove (⚠️ loses data unless using volumes)
docker rm -f cpp-rag-mcp cpp-rag-postgres
```

**Podman:**
```bash
# Start
podman start cpp-rag-mcp cpp-rag-postgres

# Stop
podman stop cpp-rag-mcp cpp-rag-postgres

# Restart
podman restart cpp-rag-mcp

# Remove
podman rm -f cpp-rag-mcp cpp-rag-postgres
```

---

## Monitoring

### Check Status

**Docker:**
```bash
# List running containers
docker ps

# Check health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Detailed inspection
docker inspect cpp-rag-mcp
```

**Podman:**
```bash
# List running containers
podman ps

# Check health
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Detailed inspection
podman inspect cpp-rag-mcp
```

### View Logs

**Docker:**
```bash
# All services
docker-compose logs

# Follow logs (real-time)
docker-compose logs -f

# Specific service
docker-compose logs mcp-server
docker-compose logs postgres

# Last 100 lines
docker logs --tail 100 cpp-rag-mcp

# Follow logs
docker logs -f cpp-rag-mcp
```

**Podman:**
```bash
# All services
podman-compose logs

# Follow logs (real-time)
podman-compose logs -f

# Specific service
podman-compose logs mcp-server

# Last 100 lines
podman logs --tail 100 cpp-rag-mcp

# Follow logs
podman logs -f cpp-rag-mcp
```

### Resource Usage

**Docker:**
```bash
# Stats (real-time)
docker stats

# Specific container
docker stats cpp-rag-mcp

# Disk usage
docker system df
```

**Podman:**
```bash
# Stats (real-time)
podman stats

# Specific container
podman stats cpp-rag-mcp

# Disk usage
podman system df
```

---

## Configuration

### Environment Variables

```bash
# Edit .env file
nano .env  # or code .env

# Apply changes (restart required)
docker-compose down && docker-compose up -d
```

### Access Web UI

```bash
# Default URL
http://localhost:8000

# Or with IP
http://127.0.0.1:8000

# Check if accessible
curl http://localhost:8000/api/status
```

### Execute Commands in Container

**Docker:**
```bash
# Interactive shell
docker exec -it cpp-rag-mcp /bin/bash

# Run command
docker exec cpp-rag-mcp ls -la /host

# Check Python environment
docker exec cpp-rag-mcp python --version
```

**Podman:**
```bash
# Interactive shell
podman exec -it cpp-rag-mcp /bin/bash

# Run command
podman exec cpp-rag-mcp ls -la /host

# Check Python environment
podman exec cpp-rag-mcp python --version
```

### Database Access

**Docker:**
```bash
# Connect to PostgreSQL
docker exec -it cpp-rag-postgres psql -U postgres -d cpp_codebase

# Backup database
docker exec cpp-rag-postgres pg_dump -U postgres cpp_codebase > backup.sql

# Restore database
docker exec -i cpp-rag-postgres psql -U postgres cpp_codebase < backup.sql
```

**Podman:**
```bash
# Connect to PostgreSQL
podman exec -it cpp-rag-postgres psql -U postgres -d cpp_codebase

# Backup database
podman exec cpp-rag-postgres pg_dump -U postgres cpp_codebase > backup.sql

# Restore database
podman exec -i cpp-rag-postgres psql -U postgres cpp_codebase < backup.sql
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs cpp-rag-mcp
podman logs cpp-rag-mcp

# Check if port is in use
# Windows
netstat -ano | findstr :8000
# Linux/Mac
lsof -i :8000

# Check container status
docker ps -a
podman ps -a
```

### Can't Access Web UI

```bash
# Verify container is running
docker ps | grep cpp-rag-mcp
podman ps | grep cpp-rag-mcp

# Check health
curl http://localhost:8000/api/status

# Try alternative URL
curl http://127.0.0.1:8000/api/status

# Check firewall (Windows)
netsh advfirewall firewall show rule name=all | findstr 8000
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres
podman ps | grep postgres

# Check PostgreSQL health
docker exec cpp-rag-postgres pg_isready -U postgres
podman exec cpp-rag-postgres pg_isready -U postgres

# View PostgreSQL logs
docker logs cpp-rag-postgres
podman logs cpp-rag-postgres

# Restart PostgreSQL
docker restart cpp-rag-postgres
podman restart cpp-rag-postgres
```

### Volume Mount Issues

```bash
# Check if volume is mounted
docker exec cpp-rag-mcp ls -la /host
podman exec cpp-rag-mcp ls -la /host

# Verify volume exists
docker volume ls
podman volume ls

# Inspect volume
docker volume inspect cpp_rag_config
podman volume inspect cpp_rag_config
```

### Reset Everything

```bash
# Docker
docker-compose down -v
docker system prune -a --volumes -f
# Then restart

# Podman
podman-compose down -v
podman system prune -a --volumes -f
# Then restart
```

---

## Maintenance

### Update to Latest Version

**Docker:**
```bash
# Pull latest image
docker pull YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest

# Recreate container
docker-compose down
docker-compose up -d
```

**Podman:**
```bash
# Pull latest image
podman pull YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest

# Recreate container
podman-compose down
podman-compose up -d
```

### Backup

```bash
# Backup database
docker exec cpp-rag-postgres pg_dump -U postgres cpp_codebase > backup-$(date +%Y%m%d).sql

# Backup configuration volume
docker run --rm -v cpp_rag_config:/data -v $(pwd):/backup alpine tar czf /backup/config-backup.tar.gz -C /data .

# Podman equivalent
podman run --rm -v cpp_rag_config:/data -v $(pwd):/backup alpine tar czf /backup/config-backup.tar.gz -C /data .
```

### Clean Up

```bash
# Remove unused images
docker image prune -a
podman image prune -a

# Remove unused volumes
docker volume prune
podman volume prune

# Remove everything (⚠️ be careful)
docker system prune -a --volumes
podman system prune -a --volumes
```

### View Image Info

```bash
# List images
docker images | grep cpp-graph-rag-mcp
podman images | grep cpp-graph-rag-mcp

# Image history
docker history YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
podman history YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest

# Image size
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
podman images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
```

---

## Common API Endpoints

```bash
# Health check
curl http://localhost:8000/api/status

# List MCP tools
curl http://localhost:8000/api/tools/list

# Get indexing status
curl http://localhost:8000/api/indexing/status

# Search code (example)
curl -X POST http://localhost:8000/api/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"search_code","arguments":{"query":"database connection"}}'
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_PATH` | `./code` | Path to your C++ source code |
| `MCP_PORT` | `8000` | Port for MCP server and web UI |
| `DB_NAME` | `cpp_codebase` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL username |
| `DB_PASSWORD` | `postgres` | PostgreSQL password |
| `DB_PORT_EXTERNAL` | `5432` | External PostgreSQL port |
| `MONITORED_PATHS` | (empty) | Paths to monitor (comma-separated) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |

---

## Port Reference

| Port | Service | Description |
|------|---------|-------------|
| `8000` | MCP Server | HTTP API and Web UI |
| `5432` | PostgreSQL | Database (optional external access) |

---

## Volume Reference

| Volume | Purpose | Backup Needed |
|--------|---------|---------------|
| `postgres_data` | Database storage | ✓ Yes |
| `cpp_rag_config` | Server configuration | ✓ Yes |
| `/host` (mount) | Source code | Read-only |

---

## Quick Debugging Commands

```bash
# Full diagnostic
docker-compose ps
docker-compose logs --tail=50
curl http://localhost:8000/api/status
docker exec cpp-rag-mcp ls -la /host
docker exec cpp-rag-postgres pg_isready -U postgres

# Podman equivalent
podman-compose ps
podman-compose logs --tail=50
curl http://localhost:8000/api/status
podman exec cpp-rag-mcp ls -la /host
podman exec cpp-rag-postgres pg_isready -U postgres
```

---

## Resources

- **Docker Docs**: https://docs.docker.com
- **Podman Docs**: https://docs.podman.io
- **Docker Hub**: https://hub.docker.com
- **Full Documentation**: See README.md and docs/ folder
