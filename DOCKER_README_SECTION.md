# Docker Installation Section
# Add this section to your main README.md

---

## 🐳 Docker Deployment (Recommended)

The easiest way to use the C++ Graph-RAG MCP Server is via Docker. No building or dependency management required!

### Quick Start

#### Prerequisites

Choose one:
- **Docker Desktop**: https://www.docker.com/products/docker-desktop
- **Podman**: https://podman.io/getting-started/installation

#### 1. Pull the Image

```bash
docker pull YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest
```

#### 2. Create Configuration

Create a directory for your deployment:

```bash
mkdir cpp-graph-rag-mcp-deployment
cd cpp-graph-rag-mcp-deployment
```

Download `docker-compose.production.yml` from the repository, or create it manually (see repository).

Create a `.env` file:

```bash
# Your source code path
HOST_PATH=C:/Projects/MyCppProject  # Windows
# HOST_PATH=/home/user/projects     # Linux

# Docker Hub image
DOCKER_IMAGE=YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest

# Port for web UI
MCP_PORT=8000

# Database settings (defaults are fine for local use)
DB_NAME=cpp_codebase
DB_USER=postgres
DB_PASSWORD=postgres
```

#### 3. Start Services

```bash
# Docker
docker-compose -f docker-compose.production.yml up -d

# Podman
podman-compose -f docker-compose.production.yml up -d
```

#### 4. Access Web UI

Open your browser: http://localhost:8000

Configure paths to monitor and start indexing!

### What You Get

✓ **Pre-built image** with all dependencies (~1.5GB)  
✓ **Embedding models** pre-downloaded (saves ~2 minutes on startup)  
✓ **PostgreSQL** with pgvector extension  
✓ **Web UI** for easy configuration  
✓ **MCP API** for integration with AI tools  
✓ **Auto-indexing** of your C++ codebase  

### Documentation

- **Quick Start**: [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) - For end users
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common commands
- **Deployment Guide**: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) - Complete workflow
- **Publishing**: [PUBLISHING.md](PUBLISHING.md) - For maintainers

### Traditional Installation

If you prefer to build from source, see the [Development Setup](#development-setup) section below.

---
