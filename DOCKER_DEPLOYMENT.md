# Docker Deployment Guide - Complete Workflow

This document provides a complete workflow for deploying the C++ Graph-RAG MCP Server using Docker/Podman, from building to publishing to running in production.

## Overview

The deployment strategy:
1. **Build** multi-stage Docker image (optimized for size and speed)
2. **Test** locally with Podman or Docker
3. **Publish** to Docker Hub for public distribution
4. **Deploy** on user machines with simple pull + run

## For Developers: Building and Publishing

### Step 1: Prepare Your Environment

#### Option A: Using Podman (Recommended)

**Windows:**
```powershell
# Install Podman Desktop
winget install RedHat.Podman-Desktop

# Or using Chocolatey
choco install podman-desktop
```

**Linux:**
```bash
# Fedora/RHEL
sudo dnf install podman

# Ubuntu/Debian
sudo apt-get install podman
```

**Mac:**
```bash
brew install podman
podman machine init
podman machine start
```

#### Option B: Using Docker

Download and install Docker Desktop from: https://www.docker.com/products/docker-desktop

### Step 2: Build the Image

The project includes automated build scripts for convenience.

#### Using PowerShell (Windows)

```powershell
# Navigate to project directory
cd c:\repos\cpp-graph-rag-mcp

# Build and publish (replace with your Docker Hub username)
.\build-and-publish.ps1 -Version "1.0.0" -DockerHubUsername "yourusername"
```

#### Using Bash (Linux/Mac/WSL)

```bash
# Navigate to project directory
cd /path/to/cpp-graph-rag-mcp

# Make script executable
chmod +x build-and-publish.sh

# Build and publish (replace with your Docker Hub username)
./build-and-publish.sh 1.0.0 yourusername
```

#### Manual Build

If you prefer manual control:

```bash
# Set variables
export DOCKER_HUB_USERNAME="yourusername"
export VERSION="1.0.0"
export IMAGE_NAME="cpp-graph-rag-mcp"

# Choose your tool (podman or docker)
TOOL=podman  # or docker

# Build
$TOOL build -t ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION} .

# Tag as latest
$TOOL tag ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION} \
           ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:latest

# Login to Docker Hub
$TOOL login docker.io

# Push
$TOOL push ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}
$TOOL push ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:latest
```

### Step 3: Verify Build

```bash
# Check image exists
podman images | grep cpp-graph-rag-mcp
# or
docker images | grep cpp-graph-rag-mcp

# Expected output should show ~1.5GB image
```

### Step 4: Local Testing

Before publishing, test the image:

```bash
# Copy production compose file
cp docker-compose.production.yml docker-compose.test.yml

# Edit to use your local image
# Change: image: ${DOCKER_IMAGE:-YOUR_DOCKERHUB_USERNAME/cpp-graph-rag-mcp:latest}
# To: image: yourusername/cpp-graph-rag-mcp:1.0.0

# Test with compose
podman-compose -f docker-compose.test.yml up -d

# Check logs
podman-compose -f docker-compose.test.yml logs -f

# Verify web UI works
curl http://localhost:8000/api/status

# Clean up
podman-compose -f docker-compose.test.yml down -v
```

### Step 5: Publish to Docker Hub

If you used the build scripts, this is done automatically. Otherwise:

```bash
# Login
podman login docker.io
# Enter your Docker Hub credentials

# Push
podman push yourusername/cpp-graph-rag-mcp:1.0.0
podman push yourusername/cpp-graph-rag-mcp:latest
```

### Step 6: Update Documentation

After publishing, update these files with your Docker Hub username:
- `docker-compose.production.yml` - Update image name
- `env.production.example` - Update DOCKER_IMAGE default
- `DOCKER_QUICKSTART.md` - Update all examples
- `README.md` - Add Docker installation section

### Step 7: Create GitHub Release

```bash
# Tag the release
git tag -a v1.0.0 -m "Release 1.0.0 - Docker images available"
git push origin v1.0.0

# Create release on GitHub with:
# - Release notes
# - Link to Docker Hub
# - Installation instructions
```

## For End Users: Running the Image

### Quick Start (Recommended)

#### Step 1: Install Docker or Podman

**Docker Desktop:**
- Download from: https://www.docker.com/products/docker-desktop
- Follow installation wizard
- Ensure it's running

**Podman:**
- Windows: `winget install RedHat.Podman-Desktop`
- Linux: `sudo dnf install podman` or `sudo apt install podman`
- Mac: `brew install podman && podman machine init && podman machine start`

#### Step 2: Create Project Directory

```bash
# Create directory
mkdir cpp-graph-rag-mcp-deployment
cd cpp-graph-rag-mcp-deployment
```

#### Step 3: Download Configuration

Download these files from the repository:
- `docker-compose.production.yml`
- `env.production.example`

Or create manually (see file contents in repository).

#### Step 4: Configure

```bash
# Copy environment template
cp env.production.example .env

# Edit .env with your settings
# Windows: notepad .env
# Linux/Mac: nano .env

# Key settings to change:
# - DOCKER_IMAGE=yourusername/cpp-graph-rag-mcp:latest
# - HOST_PATH=C:/YourProjects  (or /home/user/projects on Linux)
# - MCP_PORT=8000
```

#### Step 5: Start Services

**Using Docker:**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**Using Podman:**
```bash
podman-compose -f docker-compose.production.yml up -d
```

#### Step 6: Access Web UI

Open browser: http://localhost:8000

Configure paths and start indexing!

### Alternative: Manual Run (Without Compose)

#### Using Podman

```bash
# Create network
podman network create cpp-rag-network

# Create volumes
podman volume create postgres_data
podman volume create cpp_rag_config

# Start PostgreSQL
podman run -d \
  --name cpp-rag-postgres \
  --network cpp-rag-network \
  -e POSTGRES_DB=cpp_codebase \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -v postgres_data:/var/lib/postgresql \
  -p 5432:5432 \
  docker.io/pgvector/pgvector:pg18-trixie

# Wait 10 seconds for PostgreSQL to initialize
sleep 10

# Start MCP Server
podman run -d \
  --name cpp-rag-mcp \
  --network cpp-rag-network \
  -e DB_HOST=cpp-rag-postgres \
  -e DB_PORT=5432 \
  -e DB_NAME=cpp_codebase \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  -v C:/YourProjects:/host:ro \
  -v cpp_rag_config:/app/config \
  -p 8000:8000 \
  yourusername/cpp-graph-rag-mcp:latest
```

#### Using Docker

Same commands as Podman, just replace `podman` with `docker`.

## Architecture

### Multi-Stage Build

The Dockerfile uses a multi-stage build for optimization:

```
┌─────────────────────────────────────────┐
│ Stage 1: Builder                        │
│ - Base: python:3.11-slim                │
│ - Install build tools (gcc, g++, git)   │
│ - Create virtual environment            │
│ - Install Python dependencies           │
│ - Download embedding models (~90MB)     │
│ - Download tree-sitter grammars         │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Stage 2: Production                     │
│ - Base: python:3.11-slim                │
│ - Copy virtual env from builder         │
│ - Copy pre-downloaded models            │
│ - Copy application code                 │
│ - No build tools (smaller, safer)       │
│ - Final size: ~1.5GB                    │
└─────────────────────────────────────────┘
```

**Benefits:**
- ✓ Smaller final image (~1.5GB vs ~3GB)
- ✓ Faster startup (models pre-downloaded)
- ✓ More secure (no build tools in production)
- ✓ Better caching (dependencies layer cached)

### Container Architecture

```
┌────────────────────────────────────────────────────┐
│ Docker/Podman Network: cpp-rag-network             │
│                                                    │
│  ┌──────────────────────┐  ┌────────────────────┐ │
│  │ PostgreSQL           │  │ MCP Server         │ │
│  │ pgvector/pgvector    │  │ cpp-graph-rag-mcp  │ │
│  │                      │  │                    │ │
│  │ Port: 5432           │◄─┤ Port: 8000         │ │
│  │ Volume: postgres_data│  │ Volume: config     │ │
│  └──────────────────────┘  │ Mount: /host (ro)  │ │
│                            └────────────────────┘ │
└────────────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Host Machine          │
         │                       │
         │ Port 8000: Web UI     │
         │ Port 5432: DB (opt)   │
         │ Volume: Source Code   │
         └───────────────────────┘
```

### Volume Strategy

1. **postgres_data**: Named volume for database persistence
   - Survives container restarts
   - Backed up for production

2. **cpp_rag_config**: Named volume for server configuration
   - Stores monitored paths
   - Stores indexing state
   - Survives container restarts

3. **/host mount**: Bind mount for source code
   - Read-only for safety
   - User specifies path via HOST_PATH
   - Can be entire drive or specific directory

## Best Practices

### Security

1. **Change default passwords** in production:
   ```bash
   # In .env
   DB_PASSWORD=strong-random-password-here
   ```

2. **Don't expose database externally** in production:
   ```bash
   # In .env
   DB_PORT_EXTERNAL=
   ```

3. **Use read-only mounts** for source code:
   ```bash
   # Always use :ro suffix
   - C:/Projects:/host:ro
   ```

4. **Keep images updated**:
   ```bash
   # Pull latest periodically
   podman pull yourusername/cpp-graph-rag-mcp:latest
   podman-compose down && podman-compose up -d
   ```

### Performance

1. **Mount specific directories** instead of entire drives:
   ```bash
   # Good
   HOST_PATH=C:/Projects/MyApp
   
   # Less efficient
   HOST_PATH=C:/
   ```

2. **Allocate sufficient resources** in Docker Desktop:
   - Settings > Resources > Advanced
   - RAM: At least 4GB for large codebases
   - CPUs: 2-4 cores recommended

3. **Use SSD storage** for volumes:
   - Significant impact on database performance
   - Faster indexing

4. **Exclude build directories** via web UI:
   - Don't index `build/`, `bin/`, `obj/`
   - Reduces indexing time and database size

### Maintenance

1. **Regular backups**:
   ```bash
   # Backup database
   podman exec cpp-rag-postgres pg_dump -U postgres cpp_codebase > backup.sql
   
   # Backup config
   podman run --rm -v cpp_rag_config:/data -v $(pwd):/backup alpine \
     tar czf /backup/config.tar.gz -C /data .
   ```

2. **Monitor logs**:
   ```bash
   podman-compose logs -f --tail=100
   ```

3. **Check health**:
   ```bash
   curl http://localhost:8000/api/status
   ```

4. **Update regularly**:
   ```bash
   podman pull yourusername/cpp-graph-rag-mcp:latest
   podman-compose down && podman-compose up -d
   ```

## Troubleshooting

### Build Issues

| Problem | Solution |
|---------|----------|
| Build is very slow | Use `--cache-from` flag, check internet connection |
| Out of disk space | Run `podman system prune -a` |
| Model download fails | Check internet, retry build |
| Permission errors | Run with elevated privileges if needed |

### Runtime Issues

| Problem | Solution |
|---------|----------|
| Container won't start | Check logs: `podman logs cpp-rag-mcp` |
| Can't access web UI | Verify port 8000 not in use, check firewall |
| Database connection fails | Ensure PostgreSQL is healthy, check network |
| Volume mount is empty | Verify HOST_PATH exists and has read permissions |

### Platform-Specific

#### Windows + Docker Desktop

- Enable drive sharing: Settings > Resources > File Sharing
- Add your drive (C:, D:, etc.) to allowed mounts
- Restart Docker Desktop after changes

#### WSL2

- Use Linux-style paths: `/mnt/c/Projects` instead of `C:/Projects`
- Ensure WSL2 integration is enabled in Docker Desktop

#### SELinux (Fedora/RHEL)

- Add `:z` or `:Z` to volume mounts:
  ```bash
  -v /path/to/code:/host:ro,z
  ```

## Migration Scenarios

### From Local Development to Docker

1. Export your configuration:
   ```bash
   # Backup local config if exists
   cp -r ~/.cpp-graph-rag-mcp ./config-backup
   ```

2. Start with Docker, then import config via web UI

3. Reindex your codebase (first-time setup)

### From Docker to Docker (Different Machine)

1. Backup volumes on source machine:
   ```bash
   podman exec cpp-rag-postgres pg_dump -U postgres cpp_codebase > backup.sql
   ```

2. Copy backup.sql to target machine

3. Start containers on target machine

4. Restore:
   ```bash
   podman exec -i cpp-rag-postgres psql -U postgres cpp_codebase < backup.sql
   ```

## CI/CD Integration

See `PUBLISHING.md` for GitHub Actions workflow examples.

## Support and Resources

- **Quick Reference**: See `QUICK_REFERENCE.md` for common commands
- **User Guide**: See `DOCKER_QUICKSTART.md` for end-user instructions
- **Publishing Guide**: See `PUBLISHING.md` for detailed publishing instructions
- **Full Documentation**: See `README.md` and `docs/` folder

## Appendix: File Structure

```
cpp-graph-rag-mcp/
├── Dockerfile                      # Multi-stage build configuration
├── .dockerignore                   # Files to exclude from build
├── docker-compose.yml              # Development compose file (builds locally)
├── docker-compose.production.yml   # Production compose file (uses Docker Hub)
├── env.example                     # Development environment template
├── env.production.example          # Production environment template
├── build-and-publish.sh            # Build script for Linux/Mac
├── build-and-publish.ps1           # Build script for Windows
├── DOCKER_QUICKSTART.md            # End-user quick start guide
├── DOCKER_DEPLOYMENT.md            # This file
├── PUBLISHING.md                   # Publishing guide for maintainers
├── QUICK_REFERENCE.md              # Command reference
└── README.md                       # Main documentation
```

## Next Steps

1. **For Project Maintainers**: 
   - Review `PUBLISHING.md`
   - Build and publish first release
   - Update all docs with your Docker Hub username

2. **For End Users**:
   - Follow `DOCKER_QUICKSTART.md`
   - Pull and run the image
   - Configure paths via web UI

3. **For Developers**:
   - Review `README.md` for full features
   - Check `docs/` for integration guides
   - Start indexing your C++ codebase!
