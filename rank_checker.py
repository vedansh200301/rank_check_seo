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

# Cache for storing API responses to avoid redundant calls
ranking_cache = {}

def get_ranking(client, keyword, target_url, location_code, language_code="en", location_name='', device='desktop'):
    """Get the ranking of a target URL for a specific keyword."""
    # Create a cache key based on all parameters
    cache_key = f"{keyword}_{target_url}_{location_code}_{language_code}_{location_name}_{device}"
    
    # Check if we have a cached result
    if cache_key in ranking_cache:
        print(f"  Using cached result for '{keyword}'")
        return ranking_cache[cache_key]
    
    post_data = dict()
    post_data[len(post_data)] = dict(
        language_code=language_code,
        location_code=location_code,
        keyword=keyword,
        calculate_rectangles=True,
        device=device
    )
    
    # Add geo_location if provided
    if location_name:
        post_data[len(post_data)-1]['geo_location'] = location_name
    
    # Simplified logging
    print(f"  Searching for '{keyword}' ({device}, location: {location_code})")
    
    # Add a delay to avoid hitting API rate limits
    time.sleep(2)
    
    try:
        response = client.post("/v3/serp/google/organic/live/advanced", post_data)
        
        if response["status_code"] == 20000:
            # Process the response to find the ranking of the target URL
            if "tasks" in response and len(response["tasks"]) > 0:
                task = response["tasks"][0]
                if "result" in task and task["result"] is not None and len(task["result"]) > 0:
                    result = task["result"][0]
                    if "items" in result and result["items"] is not None:
                        # Handle different structures of the API response
                        organic_results = []
                        
                        if isinstance(result["items"], dict) and "organic" in result["items"]:
                            if result["items"]["organic"] is not None:
                                organic_results = result["items"]["organic"]
                            else:
                                return "No results found"
                        elif isinstance(result["items"], list):
                            # If items is a list, check if any item has a type of "organic"
                            organic_results = [item for item in result["items"]
                                              if isinstance(item, dict) and item.get("type") == "organic"]
                            
                            if not organic_results:
                                return "No results found"
                        else:
                            return "No results found"
                        
                        # Process organic results to find target URL
                        target = target_url.lower()
                        target_no_www = target.replace("www.", "")
                        target_with_www = "www." + target
                        
                        for position, item in enumerate(organic_results, 1):
                            if "url" in item:
                                result_url = item["url"].lower()
                                
                                # Try different variations of the target URL
                                if (target in result_url or
                                    target_no_www in result_url or
                                    target_with_www in result_url):
                                    # Extract additional ranking metrics if available
                                    rank_info = {
                                        "position": position,
                                        "rank_group": item.get("rank_group", position),
                                        "rank_absolute": item.get("rank_absolute", position)
                                    }
                                    
                                    # Cache the result
                                    ranking_cache[cache_key] = rank_info
                                    return rank_info
                        
                        # If the URL is not found in the results
                        result = "Not in top results"
                        ranking_cache[cache_key] = result
                        return result
                    else:
                        return "No results found"
                else:
                    return "No results found"
            else:
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

def update_csv_with_rankings(csv_file, keywords_with_rankings):
    """Update the CSV file with ranking information."""
    try:
        # Read all the original data from the CSV
        all_rows = []
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            # Store the fieldnames (header)
            header = reader.fieldnames.copy() if reader.fieldnames else []
            
            # Read all rows
            for row in reader:
                all_rows.append(row)
        
        # Check if ranking columns exist in the header, if not, add them
        ranking_columns = ['Ranking', 'Rank Group', 'Rank Absolute', 'Device']
        for column in ranking_columns:
            if column not in header:
                header.append(column)
        
        # Create dictionaries to map keywords to their rankings
        rankings_dict = {}
        rank_group_dict = {}
        rank_absolute_dict = {}
        
        print("\nDebug: Processing keywords_with_rankings in update_csv_with_rankings")
        for row in keywords_with_rankings:
            keyword_column = 'Keywords' if 'Keywords' in row else 'Keyword'
            if keyword_column in row:
                keyword = row[keyword_column]
                print(f"Debug: Processing keyword: {keyword}")
                print(f"Debug: Row keys: {list(row.keys())}")
                print(f"Debug: Row values: {row}")
                
                # Check if we have ranking metrics in separate columns
                if 'Ranking' in row and 'Rank Group' in row and 'Rank Absolute' in row:
                    print(f"Debug: Found separate ranking columns")
                    rankings_dict[keyword] = row['Ranking']
                    rank_group_dict[keyword] = row['Rank Group']
                    rank_absolute_dict[keyword] = row['Rank Absolute']
                # Check if we have a dictionary in the Ranking column
                elif 'Ranking' in row and isinstance(row['Ranking'], dict):
                    print(f"Debug: Found ranking dictionary: {row['Ranking']}")
                    # If ranking is a dictionary with multiple metrics
                    rankings_dict[keyword] = row['Ranking'].get('position', 'N/A')
                    rank_group_dict[keyword] = row['Ranking'].get('rank_group', 'N/A')
                    rank_absolute_dict[keyword] = row['Ranking'].get('rank_absolute', 'N/A')
                # Just a simple ranking value
                elif 'Ranking' in row:
                    print(f"Debug: Found simple ranking: {row['Ranking']}")
                    # If ranking is just a position or string
                    rankings_dict[keyword] = row['Ranking']
                    rank_group_dict[keyword] = row.get('Rank Group', 'N/A')
                    rank_absolute_dict[keyword] = row.get('Rank Absolute', 'N/A')
                else:
                    print(f"Debug: No ranking information found")
        
        # Update the rankings in the original data
        for row in all_rows:
            keyword_column = 'Keywords' if 'Keywords' in row else 'Keyword'
            if keyword_column in row and row[keyword_column] in rankings_dict:
                keyword = row[keyword_column]
                row['Ranking'] = rankings_dict[keyword]
                row['Rank Group'] = rank_group_dict[keyword]
                row['Rank Absolute'] = rank_absolute_dict[keyword]
        
        # Write all the data back to the CSV
        with open(csv_file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_rows)
        
        # Force flush to disk
        os.fsync(file.fileno())
            
        print(f"Successfully updated {csv_file} with rankings.")
        
        # Verify the file was updated
        print(f"Verifying file update...")
        with open(csv_file, 'r') as file:
            content = file.read()
            print(f"File size: {len(content)} bytes")
    except Exception as e:
        print(f"Error updating CSV file: {e}")

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
            
            # Check if test mode is enabled
            test_mode = config.get('test_mode', False)
            
            # Get API credentials if not in test mode
            if not test_mode:
                api_credentials = config.get('api_credentials', {})
                api_login = api_credentials.get('login')
                api_password = api_credentials.get('password')
            
            # Remove the config arguments
            args.pop(config_index)  # Remove --config
            args.pop(config_index)  # Remove the value
    
    # Check for test mode
    if "--test" in args:
        test_mode = True
        test_index = args.index("--test")
        args.pop(test_index)  # Remove --test
    
    # Check for limit
    if "--limit" in args:
        limit_index = args.index("--limit")
        if limit_index + 1 < len(args):
            try:
                limit = int(args[limit_index + 1])
                print(f"Limited to first {limit} keywords")
                # Remove the limit arguments
                args.pop(limit_index)  # Remove --limit
                args.pop(limit_index)  # Remove the value
            except ValueError:
                print("Error: --limit must be followed by a number")
                sys.exit(1)
        else:
            print("Error: --limit requires a value")
            sys.exit(1)
    
    # Check for location code
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
            print("  2784 - United Arab Emirates")
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
            print("  2784 - United Arab Emirates")
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
    ranking_columns = ['Ranking', 'Rank Group', 'Rank Absolute', 'Device']
    for column in ranking_columns:
        if column not in header:
            header.append(column)
    
    # Determine the keyword column name once
    if len(keywords_data) > 0:
        if 'Keyword' in keywords_data[0]:
            keyword_column = 'Keyword'
        elif 'Keywords' in keywords_data[0]:
            keyword_column = 'Keywords'
        else:
            print("Error: CSV must contain either a 'Keyword' or 'Keywords' column.")
            sys.exit(1)
    else:
        print("Error: No keywords found in CSV file.")
        sys.exit(1)
    
    # Process keywords in batches to improve performance
    batch_size = 10  # Process 10 keywords before writing to CSV
    total_keywords = len(keywords_data)
    total_batches = (total_keywords + batch_size - 1) // batch_size
    
    for batch_index in range(total_batches):
        start_idx = batch_index * batch_size
        end_idx = min(start_idx + batch_size, total_keywords)
        batch = keywords_data[start_idx:end_idx]
        
        print(f"Processing batch {batch_index + 1}/{total_batches} (keywords {start_idx + 1}-{end_idx} of {total_keywords})")
        
        # Process each keyword in the batch
        for j, keyword_row in enumerate(batch):
            keyword = keyword_row[keyword_column]
            current_index = start_idx + j
            print(f"Processing keyword ({current_index + 1}/{total_keywords}): {keyword}")
            
            # Get ranking and add to the row data
            if test_mode:
                ranking_info = get_mock_ranking(keyword, target_url)
            else:
                ranking_info = get_ranking(client, keyword, target_url, location_code, location_name='', device='desktop')
            
            # Handle different types of ranking values
            if isinstance(ranking_info, dict):
                keyword_row['Ranking'] = ranking_info.get('position', 'N/A')
                keyword_row['Rank Group'] = ranking_info.get('rank_group', 'N/A')
                keyword_row['Rank Absolute'] = ranking_info.get('rank_absolute', 'N/A')
                keyword_row['Device'] = 'desktop'
                
                # Simplified logging
                print(f"  Found at position: {keyword_row['Ranking']}")
            else:
                keyword_row['Ranking'] = ranking_info
                keyword_row['Rank Group'] = 'N/A'
                keyword_row['Rank Absolute'] = 'N/A'
                keyword_row['Device'] = 'desktop'
            
            # Update the corresponding row in all_rows
            for row in all_rows:
                if row[keyword_column] == keyword:
                    row['Ranking'] = keyword_row['Ranking']
                    row['Rank Group'] = keyword_row['Rank Group']
                    row['Rank Absolute'] = keyword_row['Rank Absolute']
                    row['Device'] = keyword_row['Device']
                    break
        
        # Write the updated data back to the CSV file after processing the batch
        with open(csv_file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_rows)
        
        print(f"  Updated CSV file with rankings for batch {batch_index + 1}/{total_batches}")
    
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