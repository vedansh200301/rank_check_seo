#!/bin/bash
set -e

# Colors for better output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Keyword Ranking API...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
  exit 1
fi

# Create data directory if it doesn't exist
if [ ! -d "./data" ]; then
  echo -e "${YELLOW}Creating data directory...${NC}"
  mkdir -p ./data
fi

# Build and start the Docker container
echo -e "${YELLOW}Building and starting the Docker container...${NC}"
docker-compose up -d --build

# Wait for the container to start
echo -e "${YELLOW}Waiting for the API to start...${NC}"
for i in {1..30}; do
  echo -n "."
  sleep 1
  
  # Check if the API is running
  response=$(curl -s http://localhost:5001/health 2>/dev/null)
  if [[ $response == *"healthy"* ]]; then
    echo -e "\n${GREEN}✅ API is running successfully!${NC}"
    echo -e "${GREEN}You can access the API at http://localhost:5001${NC}"
    echo -e "${YELLOW}Import the Postman collection to start using the API:${NC}"
    echo -e "  ${YELLOW}Keyword_Ranking_API.postman_collection.json${NC}"
    
    # Display container info
    echo -e "\n${YELLOW}Container information:${NC}"
    docker ps --filter "name=keyword-ranking-api"
    
    exit 0
  fi
  
  # Check if container is running
  if ! docker ps --filter "name=keyword-ranking-api" --format "{{.Names}}" | grep -q "keyword-ranking-api"; then
    echo -e "\n${RED}❌ Container failed to start.${NC}"
    echo -e "${YELLOW}Checking container logs:${NC}"
    docker-compose logs
    exit 1
  fi
done

echo -e "\n${RED}❌ API failed to start within the timeout period.${NC}"
echo -e "${YELLOW}Check the logs with:${NC}"
echo -e "  ${YELLOW}docker-compose logs${NC}"
exit 1