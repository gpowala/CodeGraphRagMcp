# C++ Graph-RAG MCP Server
# Multi-stage build for optimized image size

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Download tree-sitter C++ grammar
RUN python -c "import tree_sitter_cpp"

# Create cache directories and download embedding model during build
RUN mkdir -p /root/.cache/huggingface /root/.cache/torch && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# =============================================================================
# Production image
# =============================================================================
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy pre-downloaded model caches from builder
COPY --from=builder /root/.cache /root/.cache

# Copy application code
COPY server.py .
COPY parser.py .
COPY indexer.py .
COPY crash_analyzer.py .
COPY vs_context_analyzer.py .
COPY config_manager.py .

# Copy static files for web UI
COPY static/ ./static/

# Create directories for code monitoring and config
RUN mkdir -p /code /app/config /host

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/app/config

# Expose HTTP port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# Run the server
CMD ["python", "server.py"]
