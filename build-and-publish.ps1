# =============================================================================
# Build and Publish Script for C++ Graph-RAG MCP Server (PowerShell)
# =============================================================================
# This script builds and publishes the Docker image to Docker Hub using Podman
# Compatible with both Podman and Docker
#
# Usage:
#   .\build-and-publish.ps1 -Version "1.0.0" -DockerHubUsername "myusername"
#   .\build-and-publish.ps1 -Version "latest" -DockerHubUsername "myusername"
# =============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "latest",
    
    [Parameter(Mandatory=$true)]
    [string]$DockerHubUsername
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "cpp-graph-rag-mcp"

# Detect container tool (podman or docker)
$ContainerTool = $null
if (Get-Command podman -ErrorAction SilentlyContinue) {
    $ContainerTool = "podman"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $ContainerTool = "docker"
} else {
    Write-Host "Error: Neither podman nor docker found. Please install one of them." -ForegroundColor Red
    exit 1
}

Write-Host "Using container tool: $ContainerTool" -ForegroundColor Green

# Full image name
$FullImageName = "${DockerHubUsername}/${ImageName}:${Version}"
$LatestTag = "${DockerHubUsername}/${ImageName}:latest"

Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Building and Publishing C++ Graph-RAG MCP Server" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Image Name: $FullImageName"
Write-Host "Container Tool: $ContainerTool"
Write-Host ""

# Step 1: Build the image
Write-Host "Step 1/4: Building Docker image..." -ForegroundColor Green
& $ContainerTool build `
    --tag "$FullImageName" `
    --file Dockerfile `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Build successful!" -ForegroundColor Green
Write-Host ""

# Step 2: Tag as latest if not already latest
if ($Version -ne "latest") {
    Write-Host "Step 2/4: Tagging as latest..." -ForegroundColor Green
    & $ContainerTool tag "$FullImageName" "$LatestTag"
} else {
    Write-Host "Step 2/4: Skipping latest tag (version is already latest)" -ForegroundColor Green
}
Write-Host ""

# Step 3: Login to Docker Hub
Write-Host "Step 3/4: Logging in to Docker Hub..." -ForegroundColor Green
Write-Host "Please enter your Docker Hub credentials:"
& $ContainerTool login docker.io

if ($LASTEXITCODE -ne 0) {
    Write-Host "Login failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Push the image
Write-Host "Step 4/4: Pushing images to Docker Hub..." -ForegroundColor Green
Write-Host "Pushing $FullImageName..."
& $ContainerTool push "$FullImageName"

if ($Version -ne "latest") {
    Write-Host "Pushing $LatestTag..."
    & $ContainerTool push "$LatestTag"
}

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "Successfully published to Docker Hub!" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Image is now available at:"
Write-Host "  - $FullImageName"
if ($Version -ne "latest") {
    Write-Host "  - $LatestTag"
}
Write-Host ""
Write-Host "Users can pull and run with:"
Write-Host "  $ContainerTool pull $FullImageName"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Update README.md with the new version"
$releaseMsg = "  2. Create a release tag: git tag -a v$Version -m 'Release $Version'"
Write-Host $releaseMsg
$pushMsg = "  3. Push the tag: git push origin v$Version"
Write-Host $pushMsg
