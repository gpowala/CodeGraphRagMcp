# Publishing C++ Graph-RAG MCP Server to Docker Hub

This guide explains how to build and publish the Docker image to Docker Hub for public distribution.

## Prerequisites

### Required Tools

Choose **one** of the following:
- **Podman** (recommended for this project)
  - Install: https://podman.io/getting-started/installation
  - Podman Desktop: https://podman-desktop.io/
  
- **Docker Desktop**
  - Install: https://www.docker.com/products/docker-desktop

### Docker Hub Account

1. Create a free account at https://hub.docker.com
2. Create a repository named `cpp-graph-rag-mcp`
3. Note your Docker Hub username

## Building the Image

### Method 1: Using Build Script (Recommended)

We provide build scripts for both Linux/Mac and Windows.

#### Linux/Mac/WSL

```bash
# Make script executable
chmod +x build-and-publish.sh

# Build and publish (replace with your Docker Hub username)
./build-and-publish.sh 1.0.0 yourusername

# Or for latest:
./build-and-publish.sh latest yourusername
```

#### Windows PowerShell

```powershell
# Build and publish
.\build-and-publish.ps1 -Version "1.0.0" -DockerHubUsername "yourusername"

# Or for latest:
.\build-and-publish.ps1 -Version "latest" -DockerHubUsername "yourusername"
```

The script will:
1. ✓ Build the Docker image
2. ✓ Tag it appropriately
3. ✓ Log in to Docker Hub
4. ✓ Push the image

### Method 2: Manual Build with Podman

```bash
# Set your Docker Hub username
export DOCKER_HUB_USERNAME="yourusername"
export VERSION="1.0.0"

# Build the image
podman build -t ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION} .

# Tag as latest
podman tag ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION} \
            ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:latest

# Login to Docker Hub
podman login docker.io

# Push both tags
podman push ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION}
podman push ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:latest
```

### Method 3: Manual Build with Docker

```bash
# Set your Docker Hub username
export DOCKER_HUB_USERNAME="yourusername"
export VERSION="1.0.0"

# Build the image
docker build -t ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION} .

# Tag as latest
docker tag ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION} \
           ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:latest

# Login to Docker Hub
docker login

# Push both tags
docker push ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:${VERSION}
docker push ${DOCKER_HUB_USERNAME}/cpp-graph-rag-mcp:latest
```

## Build Process Details

### Multi-Stage Build

The Dockerfile uses a multi-stage build for optimization:

1. **Builder Stage**
   - Installs build dependencies (gcc, g++, git)
   - Creates Python virtual environment
   - Installs Python dependencies
   - Pre-downloads embedding models (~90MB)
   - Downloads tree-sitter C++ grammar

2. **Production Stage**
   - Uses slim Python image
   - Copies virtual environment from builder
   - Copies pre-downloaded models (saves ~2 minutes on first run)
   - Copies application code
   - Final image size: ~1.5GB (including models)

### What's Included in the Image

- ✓ Python 3.11 runtime
- ✓ All Python dependencies (FastAPI, sentence-transformers, etc.)
- ✓ Pre-downloaded embedding model (all-MiniLM-L6-v2)
- ✓ Tree-sitter C++ grammar
- ✓ Application code (server.py, parser.py, indexer.py, etc.)
- ✓ Web UI (static files)
- ✓ Health check endpoint

### What's NOT Included

- ✗ PostgreSQL database (run separately)
- ✗ User's C++ source code (mounted at runtime)
- ✗ Configuration files (persistent volume)
- ✗ Development tools
- ✗ Documentation (README, guides)

## Testing the Image

Before publishing, test the image locally:

### Using Podman Compose

```bash
# Create test directory
mkdir test-cpp-rag
cd test-cpp-rag

# Copy docker-compose.yml and .env from project
# Edit docker-compose.yml to use your image:
#   image: yourusername/cpp-graph-rag-mcp:1.0.0

# Start services
podman-compose up -d

# Check logs
podman-compose logs -f mcp-server

# Access web UI
# Open http://localhost:8000

# Clean up
podman-compose down -v
```

### Using Docker Compose

```bash
# Same as above, but use docker-compose:
docker-compose up -d
docker-compose logs -f mcp-server
docker-compose down -v
```

### Manual Test

```bash
# Start PostgreSQL
podman run -d --name test-postgres \
  -e POSTGRES_DB=cpp_codebase \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  pgvector/pgvector:pg18-trixie

# Get PostgreSQL IP
POSTGRES_IP=$(podman inspect test-postgres | grep -m 1 '"IPAddress"' | cut -d'"' -f4)

# Start MCP server
podman run -d --name test-mcp \
  -e DB_HOST=$POSTGRES_IP \
  -e DB_PORT=5432 \
  -e DB_NAME=cpp_codebase \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  -p 8000:8000 \
  yourusername/cpp-graph-rag-mcp:1.0.0

# Check health
curl http://localhost:8000/api/status

# Clean up
podman stop test-mcp test-postgres
podman rm test-mcp test-postgres
```

## Version Management

### Semantic Versioning

Use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes (e.g., 2.0.0)
- **MINOR**: New features, backwards compatible (e.g., 1.1.0)
- **PATCH**: Bug fixes (e.g., 1.0.1)

### Recommended Tags

Always push two tags:
1. Specific version: `yourusername/cpp-graph-rag-mcp:1.0.0`
2. Latest: `yourusername/cpp-graph-rag-mcp:latest`

Example:
```bash
podman tag my-image:1.0.0 my-image:latest
podman push my-image:1.0.0
podman push my-image:latest
```

### Tag Strategy

- `latest` - Always points to the most recent stable release
- `1.0.0`, `1.1.0`, etc. - Specific releases (immutable)
- `dev` - Development/unstable builds (optional)

## Docker Hub Repository Settings

### Repository Description

```
C++ Graph-RAG MCP Server - Intelligent C++ codebase analysis with RAG and semantic search

Features:
- Semantic search across large C++ codebases
- Call graph analysis and navigation
- Crash dump analysis and root cause detection
- Real-time code indexing
- Web UI for configuration and search
- MCP (Model Context Protocol) compatible

Documentation: [Your GitHub URL]
```

### README on Docker Hub

Docker Hub supports a README. Create one with:

```markdown
# C++ Graph-RAG MCP Server

Run with Docker Compose:

```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg18-trixie
    environment:
      POSTGRES_DB: cpp_codebase
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql

  mcp-server:
    image: yourusername/cpp-graph-rag-mcp:latest
    depends_on:
      - postgres
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: cpp_codebase
      DB_USER: postgres
      DB_PASSWORD: postgres
    volumes:
      - /path/to/your/cpp/code:/host:ro
      - config:/app/config
    ports:
      - "8000:8000"

volumes:
  postgres_data:
  config:
```

Quick Start:
```bash
docker-compose up -d
```

Access web UI: http://localhost:8000

Full documentation: [Your GitHub URL]
```

## Continuous Integration (Optional)

### GitHub Actions Example

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Publish Docker Image

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Extract version
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            yourusername/cpp-graph-rag-mcp:${{ steps.version.outputs.VERSION }}
            yourusername/cpp-graph-rag-mcp:latest
          cache-from: type=registry,ref=yourusername/cpp-graph-rag-mcp:latest
          cache-to: type=inline
```

Required secrets in GitHub:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` (create at https://hub.docker.com/settings/security)

## Troubleshooting

### Build Issues

**Problem**: Build is slow
- **Solution**: Use `--cache-from` to reuse previous layers
  ```bash
  podman build --cache-from yourusername/cpp-graph-rag-mcp:latest .
  ```

**Problem**: Out of disk space
- **Solution**: Clean up old images
  ```bash
  podman system prune -a --volumes
  ```

**Problem**: Model download fails
- **Solution**: Check internet connection, retry build
- The embedding model is ~90MB, ensure stable connection

### Push Issues

**Problem**: Authentication failed
- **Solution**: Login again
  ```bash
  podman logout docker.io
  podman login docker.io
  ```

**Problem**: Push denied
- **Solution**: Verify repository exists on Docker Hub
- Ensure you have push permissions

**Problem**: Layer too large
- **Solution**: Check .dockerignore is in place
- The image should be ~1.5GB final size

## Post-Publishing Checklist

After publishing to Docker Hub:

- [ ] Update DOCKER_QUICKSTART.md with your Docker Hub username
- [ ] Update README.md with pull instructions
- [ ] Create Git tag for the release
  ```bash
  git tag -a v1.0.0 -m "Release 1.0.0"
  git push origin v1.0.0
  ```
- [ ] Create GitHub release with:
  - Release notes
  - Link to Docker Hub image
  - Installation instructions
- [ ] Test pulling and running from Docker Hub
  ```bash
  podman pull yourusername/cpp-graph-rag-mcp:latest
  ```
- [ ] Update documentation with example docker-compose.yml using published image
- [ ] Announce the release (if applicable)

## Security Considerations

1. **Secrets**: Never include secrets in the image
   - Use environment variables for sensitive data
   - Don't commit `.env` files

2. **Image Scanning**: Consider scanning for vulnerabilities
   ```bash
   # Using Trivy
   podman run --rm -v /var/run/docker.sock:/var/run/docker.sock \
     aquasec/trivy image yourusername/cpp-graph-rag-mcp:latest
   ```

3. **Base Image Updates**: Regularly rebuild with updated base images
   - Python 3.11-slim receives security updates
   - Rebuild monthly or after security announcements

4. **Private vs Public**: 
   - Public: Anyone can pull the image
   - Private: Requires Docker Hub login (paid feature)

## Resources

- Docker Hub: https://hub.docker.com
- Podman Documentation: https://docs.podman.io
- Docker Documentation: https://docs.docker.com
- Multi-stage builds: https://docs.docker.com/build/building/multi-stage/
- Best practices: https://docs.docker.com/develop/dev-best-practices/

## Support

For issues with building or publishing:
1. Check build logs for specific errors
2. Review Docker Hub status page
3. Open an issue in the project repository
