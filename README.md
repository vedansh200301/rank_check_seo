# Keyword Ranking Checker API

This microservice checks the ranking of a specific website URL for keywords using the DataForSEO API. It provides both a command-line script and a REST API.

## Files

### Core Files
- `rank_checker.py`: Main script that processes keywords and updates the CSV with ranking information
- `app.py`: Flask API wrapper for the ranking script
- `client.py`: DataForSEO API client library
- `config.json`: Configuration file for the script

### Docker Files
- `Dockerfile`: Instructions for building the Docker image
- `docker-compose.yml`: Configuration for running the Docker container
- `requirements.txt`: Python dependencies

### API Documentation
- `Keyword_Ranking_API.postman_collection.json`: Postman collection for API testing

## Requirements

- Python 3.6 or higher
- DataForSEO API credentials (login and password)
- Docker (for containerized deployment)

## Usage

### Configuration File Mode (Recommended)

The easiest way to use the script is with a JSON configuration file:

```bash
python rank_checker.py --config config.json
```

#### Example Configuration File:

```json
{
  "csv_file": "/path/to/your/keywords.csv",
  "target_url": "example.com",
  "api_credentials": {
    "login": "your_api_login",
    "password": "your_api_password"
  },
  "location_code": 2356,
  "limit": 100
}
```

#### Configuration Options:

- `csv_file`: Path to the CSV file containing keywords (required)
- `target_url`: The website URL for which you want to check rankings (required)
- `api_credentials`: Your DataForSEO API credentials (required unless test_mode is true)
  - `login`: Your DataForSEO API login
  - `password`: Your DataForSEO API password
- `location_code`: Location code for the search (optional, default: 2840 - USA)
  - 2356 - India
  - 2840 - United States
  - 2826 - United Kingdom
  - 2036 - Australia
  - 2124 - Canada
- `limit`: Maximum number of keywords to process (optional)
- `test_mode`: Set to true to use simulated API responses (optional, default: false)

### Command Line Mode

#### Normal Mode (requires DataForSEO API credentials)

```bash
python rank_checker.py <csv_file> <target_url> <api_login> <api_password> [--limit <number>] [--location <code>]
```

##### Parameters:

- `<csv_file>`: Path to the CSV file containing keywords (must have a "Keyword" or "Keywords" column)
- `<target_url>`: The website URL for which you want to check rankings (e.g., "example.com")
- `<api_login>`: Your DataForSEO API login
- `<api_password>`: Your DataForSEO API password
- `--limit <number>`: Optional parameter to limit the number of keywords to process
- `--location <code>`: Optional parameter to specify the location code (default: 2840 - USA)

##### Example:

```bash
python rank_checker.py keywords.csv example.com your_login your_password --location 2356 --limit 100
```

#### Test Mode (no API credentials required)

For testing or demonstration purposes, you can run the script in test mode, which uses simulated API responses:

```bash
python rank_checker.py --test <csv_file> <target_url> [--limit <number>] [--location <code>]
```

##### Example:

```bash
python rank_checker.py --test keywords.csv example.com --location 2356
```

In test mode, the script generates mock ranking data based on the keywords, allowing you to see how the script works without needing actual API credentials.

## CSV Format

The input CSV file must have at least a "Keyword" or "Keywords" column. The script will add the following columns with ranking information:

- `Ranking`: The position of the target URL in the search results
- `Rank Group`: The group ranking from DataForSEO
- `Rank Absolute`: The absolute ranking from DataForSEO

Example input CSV:
```
Keywords
albert einstein
theory of relativity
famous scientists
```

Example output CSV after running the script:
```
Keywords,Ranking,Rank Group,Rank Absolute
albert einstein,3,3,4
theory of relativity,5,5,7
famous scientists,Not in top results,N/A,N/A
```

The ranking metrics provide different perspectives on the position:
- `Ranking`: The position in the list of organic results
- `Rank Group`: Similar results are grouped together
- `Rank Absolute`: The absolute position including all result types (ads, featured snippets, etc.)

## Notes

- The script adds a 1-second delay between API calls to avoid hitting rate limits
- If the target URL is not found in the search results, "Not in top results" will be recorded
- API errors will be logged to the console

## REST API

The microservice provides a REST API that can be used without any knowledge of Python or coding.

### Running the API

#### Using Docker (Recommended)

1. Build and start the Docker container:
   ```bash
   docker-compose up -d
   ```

2. The API will be available at http://localhost:5001

#### Without Docker

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Flask application:
   ```bash
   python app.py
   ```

### API Endpoints

#### Health Check
- **URL**: `/health`
- **Method**: `GET`
- **Description**: Check if the API is running
- **Response**: `{"status": "healthy"}`

#### Check Rankings
- **URL**: `/check-rankings`
- **Method**: `POST`
- **Description**: Check rankings for keywords

##### Option 1: JSON Payload
- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "target_url": "example.com",
    "api_credentials": {
      "login": "your_api_login",
      "password": "your_api_password"
    },
    "location_code": 2356,
    "limit": 10,
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }
  ```
- **Response**: JSON with ranking results

##### Option 2: CSV Upload
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `csv_file`: CSV file with keywords
  - `config`: JSON configuration
    ```json
    {
      "target_url": "example.com",
      "api_credentials": {
        "login": "your_api_login",
        "password": "your_api_password"
      },
      "location_code": 2356,
      "limit": 10
    }
    ```
- **Response**: JSON with ranking results and updated CSV content

### Using Postman

1. Import the `Keyword_Ranking_API.postman_collection.json` file into Postman
2. Set the `base_url` variable to your API URL (default: `http://localhost:5001`)
3. Use the pre-configured requests to interact with the API

## Docker Deployment

### Building the Docker Image

```bash
docker build -t keyword-ranking-api .
```

### Running the Docker Container

```bash
docker run -p 5001:5000 keyword-ranking-api
```

### Using Docker Compose

#### Option 1: Using the provided scripts

We've included convenient scripts to start and stop the API:

1. Start the API:
   ```bash
   ./start.sh
   ```

2. Stop the API:
   ```bash
   ./stop.sh
   ```

#### Option 2: Manual commands

1. Start the API:
   ```bash
   docker-compose up -d
   ```

2. Stop the API:
   ```bash
   docker-compose down
   ```

3. View logs:
   ```bash
   docker-compose logs
   ```