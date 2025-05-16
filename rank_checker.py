import csv
import sys
import time
import random
import json
import os
from client import RestClient

def read_keywords_from_csv(csv_file):
    """Read keywords from a CSV file."""
    keywords = []
    try:
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                keywords.append(row)
        return keywords
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

def get_ranking(client, keyword, target_url, location_code, language_code="en"):
    """Get the ranking of a target URL for a specific keyword."""
    post_data = dict()
    post_data[len(post_data)] = dict(
        language_code=language_code,
        location_code=location_code,
        keyword=keyword,
        calculate_rectangles=True
    )
    
    print(f"  Searching for '{keyword}' with location code: {location_code}")
    
    try:
        response = client.post("/v3/serp/google/organic/live/advanced", post_data)
        
        # Print the entire response for the first keyword for debugging
        if keyword == "registerkaro gurgaon":
            print("\nAPI Response for first keyword:")
            print(f"Status Code: {response.get('status_code')}")
            print(f"Status Message: {response.get('status_message')}")
            if "tasks" in response:
                print(f"Number of tasks: {len(response['tasks'])}")
                if len(response['tasks']) > 0 and "result" in response['tasks'][0]:
                    print(f"Number of results: {len(response['tasks'][0]['result'])}")
                    if len(response['tasks'][0]['result']) > 0:
                        result = response['tasks'][0]['result'][0]
                        print(f"Result structure: {list(result.keys())}")
                        if "items" in result:
                            print(f"Items type: {type(result['items'])}")
                            if isinstance(result['items'], dict):
                                print(f"Items keys: {list(result['items'].keys())}")
                                if "organic" in result['items']:
                                    print(f"Number of organic results: {len(result['items']['organic'])}")
                                else:
                                    print("No organic results found in items dictionary")
                            elif isinstance(result['items'], list):
                                print(f"Items list length: {len(result['items'])}")
                                if len(result['items']) > 0:
                                    print(f"First item type: {type(result['items'][0])}")
                                    if isinstance(result['items'][0], dict):
                                        print(f"First item keys: {list(result['items'][0].keys())}")
                            else:
                                print(f"Items is of unexpected type: {type(result['items'])}")
                        else:
                            print("No items found in result")
            else:
                print("No tasks found in response")
        
        if response["status_code"] == 20000:
            # Process the response to find the ranking of the target URL
            if "tasks" in response and len(response["tasks"]) > 0:
                task = response["tasks"][0]
                if "result" in task and len(task["result"]) > 0:
                    result = task["result"][0]
                    if "items" in result:
                        # Handle different structures of the API response
                        if isinstance(result["items"], dict) and "organic" in result["items"]:
                            organic_results = result["items"]["organic"]
                            print(f"  Found {len(organic_results)} organic results for '{keyword}'")
                        elif isinstance(result["items"], list):
                            # If items is a list, check if any item has a type of "organic"
                            organic_results = []
                            for item in result["items"]:
                                if isinstance(item, dict) and item.get("type") == "organic":
                                    organic_results.append(item)
                            
                            if organic_results:
                                print(f"  Found {len(organic_results)} organic results for '{keyword}'")
                            else:
                                print(f"  No organic results found in items list for '{keyword}'")
                                return "No results found"
                        else:
                            print(f"  Unexpected items structure for '{keyword}'")
                            return "No results found"
                        
                        for position, item in enumerate(organic_results, 1):
                            if "url" in item:
                                result_url = item["url"].lower()
                                target = target_url.lower()
                                
                                # Try different variations of the target URL
                                if (target in result_url or
                                    target.replace("www.", "") in result_url or
                                    "www." + target in result_url):
                                    # Extract additional ranking metrics if available
                                    rank_info = {}
                                    rank_info["position"] = position
                                    
                                    if "rank_group" in item:
                                        rank_info["rank_group"] = item["rank_group"]
                                    
                                    if "rank_absolute" in item:
                                        rank_info["rank_absolute"] = item["rank_absolute"]
                                    
                                    # Print detailed ranking information
                                    print(f"  Found target URL at position {position}")
                                    for key, value in rank_info.items():
                                        if key != "position":
                                            print(f"    {key}: {value}")
                                    
                                    # Return a dictionary with all ranking metrics
                                    return rank_info
                                
                                # Print the first 5 results for debugging
                                if position <= 5:
                                    print(f"  Result {position}: {result_url}")
                        
                        # If the URL is not found in the results
                        return "Not in top results"
            
            return "No results found"
        else:
            print(f"API Error. Code: {response['status_code']} Message: {response['status_message']}")
            return "API Error"
    except Exception as e:
        print(f"Exception during API call: {e}")
        return "Error"

def get_mock_ranking(keyword, target_url):
    """Generate mock ranking data for testing purposes."""
    # Simulate different rankings based on keywords
    keyword_lower = keyword.lower()
    
    # Create a deterministic but seemingly random ranking based on the keyword
    # This ensures the same keyword always gets the same ranking in test mode
    random.seed(sum(ord(c) for c in keyword_lower))
    
    # 20% chance of not being in top results
    if random.random() < 0.2:
        return "Not in top results"
    
    # Generate position based on keyword
    if "einstein" in keyword_lower:
        position = random.randint(1, 5)  # High ranking for Einstein-related keywords
    elif "physics" in keyword_lower or "science" in keyword_lower:
        position = random.randint(3, 10)  # Medium ranking for science keywords
    elif "theory" in keyword_lower:
        position = random.randint(5, 15)  # Lower ranking for theory keywords
    else:
        position = random.randint(1, 30)  # Random ranking for other keywords
    
    # Create a dictionary with additional ranking metrics
    rank_info = {
        "position": position,
        "rank_group": position,  # In mock data, rank_group is the same as position
        "rank_absolute": position + random.randint(0, 2)  # Slightly different from position
    }
    
    return rank_info

class MockClient:
    """Mock client for testing without actual API credentials."""
    def __init__(self, *args, **kwargs):
        pass
        
    def post(self, endpoint, post_data):
        """Simulate a response from the DataForSEO API."""
        keyword = post_data[0]["keyword"]
        
        # Create a mock response structure similar to the actual API
        mock_response = {
            "status_code": 20000,
            "status_message": "Ok.",
            "tasks": [
                {
                    "result": [
                        {
                            "items": {
                                "organic": []
                            }
                        }
                    ]
                }
            ]
        }
        
        # Generate 10 mock search results
        for i in range(1, 11):
            result = {
                "position": i,
                "title": f"Result {i} for {keyword}",
                "url": f"https://example{i}.com/{keyword.replace(' ', '-')}"
            }
            mock_response["tasks"][0]["result"][0]["items"]["organic"].append(result)
        
        # Insert the target URL at a specific position based on the keyword
        random.seed(sum(ord(c) for c in keyword.lower()))
        position = random.randint(1, 10)
        if random.random() > 0.2:  # 80% chance of the target URL appearing in results
            mock_response["tasks"][0]["result"][0]["items"]["organic"][position-1]["url"] = f"https://{keyword.replace(' ', '-')}.{target_url}"
            
        return mock_response

# Function removed as it's no longer needed - CSV is updated in real-time for each keyword

def load_config(config_file):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
        
        # Validate required fields
        required_fields = ['csv_file', 'target_url']
        if not all(field in config for field in required_fields):
            missing = [field for field in required_fields if field not in config]
            print(f"Error: Missing required fields in config file: {', '.join(missing)}")
            sys.exit(1)
        
        # Set default values for optional fields
        if 'location_code' not in config:
            config['location_code'] = 2840  # Default to USA
        
        # Validate API credentials if not in test mode
        if 'test_mode' not in config or not config['test_mode']:
            if 'api_credentials' not in config:
                print("Error: API credentials are required when not in test mode")
                sys.exit(1)
            if not all(field in config['api_credentials'] for field in ['login', 'password']):
                print("Error: API credentials must include login and password")
                sys.exit(1)
        
        return config
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

def main():
    # Check if config file is provided
    config_file = None
    test_mode = False
    limit = None
    location_code = 2840  # Default location code (USA)
    csv_file = None
    target_url = None
    api_login = None
    api_password = None
    
    # Process command line arguments
    args = sys.argv.copy()
    
    # Check for config file
    if "--config" in args:
        config_index = args.index("--config")
        if config_index + 1 < len(args):
            config_file = args[config_index + 1]
            print(f"Loading configuration from {config_file}")
            
            # Load configuration from file
            config = load_config(config_file)
            
            # Set variables from config
            csv_file = config['csv_file']
            target_url = config['target_url']
            location_code = config.get('location_code', 2840)
            limit = config.get('limit')
            test_mode = config.get('test_mode', False)
            
            if not test_mode and 'api_credentials' in config:
                api_login = config['api_credentials'].get('login')
                api_password = config['api_credentials'].get('password')
            
            # Print configuration
            print(f"CSV file: {csv_file}")
            print(f"Target URL: {target_url}")
            print(f"Location code: {location_code}")
            if limit:
                print(f"Limit: {limit}")
            print(f"Test mode: {test_mode}")
            
            # Validate file path
            if not os.path.exists(csv_file):
                print(f"Error: CSV file not found: {csv_file}")
                sys.exit(1)
        else:
            print("Error: --config requires a value")
            sys.exit(1)
    else:
        # Process traditional command line arguments
        if "--test" in args:
            test_mode = True
            args.remove("--test")
            print("Running in TEST MODE with simulated API responses")
    
    if "--limit" in args:
        limit_index = args.index("--limit")
        if limit_index + 1 < len(args):
            try:
                limit = int(args[limit_index + 1])
                print(f"Processing only the first {limit} keywords")
                # Remove the limit argument and its value
                args.pop(limit_index)  # Remove --limit
                args.pop(limit_index)  # Remove the value
            except ValueError:
                print("Error: --limit must be followed by a number")
                sys.exit(1)
        else:
            print("Error: --limit requires a value")
            sys.exit(1)
    
    if "--location" in args:
        location_index = args.index("--location")
        if location_index + 1 < len(args):
            try:
                location_code = int(args[location_index + 1])
                print(f"Using location code: {location_code}")
                # Remove the location argument and its value
                args.pop(location_index)  # Remove --location
                args.pop(location_index)  # Remove the value
            except ValueError:
                print("Error: --location must be followed by a number")
                sys.exit(1)
        else:
            print("Error: --location requires a value")
            sys.exit(1)
    
    # Check remaining arguments if not using config file
    if config_file is None:
        if test_mode and len(args) < 3:
            print("Usage:")
            print("  python rank_checker.py --config <config_file>")
            print("  python rank_checker.py --test <csv_file> <target_url> [--limit <number>] [--location <code>]")
            print("  python rank_checker.py <csv_file> <target_url> <api_login> <api_password> [--limit <number>] [--location <code>]")
            print("\nLocation codes examples:")
            print("  2840 - United States")
            print("  2356 - India")
            print("  2826 - United Kingdom")
            print("  2036 - Australia")
            print("  2124 - Canada")
            sys.exit(1)
        elif not test_mode and len(args) < 5:
            print("Usage:")
            print("  python rank_checker.py --config <config_file>")
            print("  python rank_checker.py <csv_file> <target_url> <api_login> <api_password> [--limit <number>] [--location <code>]")
            print("  python rank_checker.py --test <csv_file> <target_url> [--limit <number>] [--location <code>]  # Test mode with mock data")
            print("\nLocation codes examples:")
            print("  2840 - United States")
            print("  2356 - India")
            print("  2826 - United Kingdom")
            print("  2036 - Australia")
            print("  2124 - Canada")
            sys.exit(1)
        
        # Get the required arguments
        csv_file = args[1]
        target_url = args[2]
        
        if not test_mode:
            api_login = args[3]
            api_password = args[4]
    
    # Initialize the client based on mode
    if test_mode:
        client = MockClient()
        print(f"Using mock client to check rankings for {target_url}")
    else:
        if not api_login or not api_password:
            print("Error: API credentials are required when not in test mode")
            sys.exit(1)
        client = RestClient(api_login, api_password)
        print(f"Using DataForSEO API to check rankings for {target_url}")
    
    # Read keywords from CSV
    keywords_data = read_keywords_from_csv(csv_file)
    
    # Apply limit if specified
    if limit and limit < len(keywords_data):
        keywords_data = keywords_data[:limit]
        print(f"Limited to first {limit} keywords")
    
    print(f"Processing {len(keywords_data)} keywords...")
    
    # Make a copy of the CSV file before updating
    backup_file = csv_file + ".backup"
    try:
        with open(csv_file, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        print(f"Created backup file: {backup_file}")
    except Exception as e:
        print(f"Warning: Could not create backup file: {e}")
    
    # Read the CSV file once to get the structure
    all_rows = []
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames.copy() if reader.fieldnames else []
        for row in reader:
            all_rows.append(row)
    
    # Check if ranking columns exist in the header, if not, add them
    ranking_columns = ['Ranking', 'Rank Group', 'Rank Absolute']
    for column in ranking_columns:
        if column not in header:
            header.append(column)
    
    # Get ranking for each keyword and update CSV immediately
    for i, keyword_row in enumerate(keywords_data):
        # Check for either 'Keyword' or 'Keywords' column
        if 'Keyword' in keyword_row:
            keyword_column = 'Keyword'
        elif 'Keywords' in keyword_row:
            keyword_column = 'Keywords'
        else:
            print("Error: CSV must contain either a 'Keyword' or 'Keywords' column.")
            sys.exit(1)
            
        keyword = keyword_row[keyword_column]
        print(f"Processing keyword ({i+1}/{len(keywords_data)}): {keyword}")
        
        # Get ranking and add to the row data
        if test_mode:
            ranking_info = get_mock_ranking(keyword, target_url)
        else:
            ranking_info = get_ranking(client, keyword, target_url, location_code)
        
        # Handle different types of ranking values
        if isinstance(ranking_info, dict):
            keyword_row['Ranking'] = ranking_info.get('position', 'N/A')
            keyword_row['Rank Group'] = ranking_info.get('rank_group', 'N/A')
            keyword_row['Rank Absolute'] = ranking_info.get('rank_absolute', 'N/A')
            
            # Print detailed ranking information for debugging
            print(f"  Storing ranking data: Position={keyword_row['Ranking']}, Rank Group={keyword_row['Rank Group']}, Rank Absolute={keyword_row['Rank Absolute']}")
        else:
            keyword_row['Ranking'] = ranking_info
            keyword_row['Rank Group'] = 'N/A'
            keyword_row['Rank Absolute'] = 'N/A'
        
        # Update the corresponding row in all_rows
        for row in all_rows:
            if row[keyword_column] == keyword:
                row['Ranking'] = keyword_row['Ranking']
                row['Rank Group'] = keyword_row['Rank Group']
                row['Rank Absolute'] = keyword_row['Rank Absolute']
                break
        
        # Write the updated data back to the CSV file immediately
        with open(csv_file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_rows)
        
        print(f"  Updated CSV file with ranking for '{keyword}'")
        
        # Add a small delay to avoid hitting API rate limits
        time.sleep(1)
    
    # Verify the file exists and has content
    try:
        file_size = os.path.getsize(csv_file)
        print(f"CSV file size after all updates: {file_size} bytes")
        if file_size == 0:
            print("Warning: CSV file is empty after update!")
    except Exception as e:
        print(f"Warning: Could not verify file size: {e}")
    
    print("Ranking check completed!")

if __name__ == "__main__":
    main()