#!/bin/bash
set -e

# Colors for better output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping Keyword Ranking API...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}Error: Docker is not running. Cannot stop containers.${NC}"
  exit 1
fi

# Check if the container is running
if ! docker ps --filter "name=keyword-ranking-api" --format "{{.Names}}" | grep -q "keyword-ranking-api"; then
  echo -e "${YELLOW}No running containers found.${NC}"
  
  # Check if the container exists but is stopped
  if docker ps -a --filter "name=keyword-ranking-api" --format "{{.Names}}" | grep -q "keyword-ranking-api"; then
    echo -e "${YELLOW}Container exists but is not running. Removing...${NC}"
    docker-compose down
  else
    echo -e "${YELLOW}No containers to stop.${NC}"
    exit 0
  fi
else
  # Stop the Docker container
  echo -e "${YELLOW}Stopping running containers...${NC}"
  docker-compose down
fi

# Verify all containers are stopped
if ! docker ps --filter "name=keyword-ranking-api" --format "{{.Names}}" | grep -q "keyword-ranking-api"; then
  echo -e "${GREEN}✅ API has been successfully stopped.${NC}"
else
  echo -e "${RED}❌ Failed to stop all containers. Try running:${NC}"
  echo -e "  ${YELLOW}docker-compose down --remove-orphans${NC}"
  exit 1
fi