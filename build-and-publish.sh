#!/usr/bin/env bash
# =============================================================================
# Build and Publish Script for C++ Graph-RAG MCP Server
# =============================================================================
# This script builds and publishes the Docker image to Docker Hub using Podman
# Compatible with both Podman and Docker
#
# Usage:
#   ./build-and-publish.sh [VERSION] [DOCKER_HUB_USERNAME]
#
# Examples:
#   ./build-and-publish.sh 1.0.0 myusername
#   ./build-and-publish.sh latest myusername
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="cpp-graph-rag-mcp"
VERSION="${1:-latest}"
DOCKER_HUB_USERNAME="${2}"

# Detect container tool (podman or docker)
if command -v podman &> /dev/null; then
    CONTAINER_TOOL="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_TOOL="docker"
else
    echo -e "${RED}Error: Neither podman nor docker found. Please install one of them.${NC}"
    exit 1
fi

echo -e "${GREEN}Using container tool: ${CONTAINER_TOOL}${NC}"

# Validate username
if [ -z "$DOCKER_HUB_USERNAME" ]; then
    echo -e "${RED}Error: Docker Hub username not provided${NC}"
    echo "Usage: $0 [VERSION] [DOCKER_HUB_USERNAME]"
    echo "Example: $0 1.0.0 myusername"
    exit 1
fi

# Full image name
FULL_IMAGE_NAME="${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
LATEST_TAG="${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:latest"

echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW}Building and Publishing C++ Graph-RAG MCP Server${NC}"
echo -e "${YELLOW}==============================================================================${NC}"
echo "Image Name: ${FULL_IMAGE_NAME}"
echo "Container Tool: ${CONTAINER_TOOL}"
echo ""

# Step 1: Build the image
echo -e "${GREEN}Step 1/4: Building Docker image...${NC}"
$CONTAINER_TOOL build \
    --tag "${FULL_IMAGE_NAME}" \
    --file Dockerfile \
    .

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Build successful!${NC}"
echo ""

# Step 2: Tag as latest if not already latest
if [ "$VERSION" != "latest" ]; then
    echo -e "${GREEN}Step 2/4: Tagging as latest...${NC}"
    $CONTAINER_TOOL tag "${FULL_IMAGE_NAME}" "${LATEST_TAG}"
else
    echo -e "${GREEN}Step 2/4: Skipping latest tag (version is already latest)${NC}"
fi
echo ""

# Step 3: Login to Docker Hub
echo -e "${GREEN}Step 3/4: Logging in to Docker Hub...${NC}"
echo "Please enter your Docker Hub credentials:"
$CONTAINER_TOOL login docker.io

if [ $? -ne 0 ]; then
    echo -e "${RED}Login failed!${NC}"
    exit 1
fi
echo ""

# Step 4: Push the image
echo -e "${GREEN}Step 4/4: Pushing images to Docker Hub...${NC}"
echo "Pushing ${FULL_IMAGE_NAME}..."
$CONTAINER_TOOL push "${FULL_IMAGE_NAME}"

if [ "$VERSION" != "latest" ]; then
    echo "Pushing ${LATEST_TAG}..."
    $CONTAINER_TOOL push "${LATEST_TAG}"
fi

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}✓ Successfully published to Docker Hub!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo "Image is now available at:"
echo "  - ${FULL_IMAGE_NAME}"
if [ "$VERSION" != "latest" ]; then
    echo "  - ${LATEST_TAG}"
fi
echo ""
echo "Users can pull and run with:"
echo "  ${CONTAINER_TOOL} pull ${FULL_IMAGE_NAME}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update README.md with the new version"
echo "  2. Create a release tag: git tag -a v${VERSION} -m 'Release ${VERSION}'"
echo "  3. Push the tag: git push origin v${VERSION}"
