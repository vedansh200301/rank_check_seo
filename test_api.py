import json
import os
from client import RestClient

def test_api():
    # Load API credentials from config.json
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            api_login = config.get("api_credentials", {}).get("login", "")
            api_password = config.get("api_credentials", {}).get("password", "")
            target_url = config.get("target_url", "registerkaro.in")
    except Exception as e:
        print(f"Error loading config.json: {e}")
        api_login = "marcom@registerkaro.in"
        api_password = "bd89ed29b2a8ce4c"
        target_url = "registerkaro.in"
    
    # Initialize the client with actual credentials
    client = RestClient(api_login, api_password)
    
    # Test parameters
    keyword = "registerkaro gurgaon"
    location_code = 2356  # India
    location_name = "delhi"
    device = "desktop"
    language_code = "en"
    
    # Create post data
    post_data = dict()
    # Try different parameter names for location_name
    post_data[len(post_data)] = dict(
        language_code=language_code,
        location_code=location_code,
        keyword=keyword,
        calculate_rectangles=True,
        device=device,
        # Try different parameter names for location
        geo_location=location_name
    )
    
    print(f"Testing API with parameters:")
    print(f"  Keyword: {keyword}")
    print(f"  Location Code: {location_code}")
    print(f"  Location Name: {location_name}")
    print(f"  Device: {device}")
    print(f"  Language Code: {language_code}")
    print(f"  Calculate Rectangles: True")
    
    # Make API request
    try:
        response = client.post("/v3/serp/google/organic/live/advanced", post_data)
        
        # Save the full response to a file for inspection
        with open("response.json", "w") as f:
            json.dump(response, f, indent=2)
        
        print("\nAPI Response:")
        print(f"Status Code: {response.get('status_code')}")
        print(f"Status Message: {response.get('status_message')}")
        
        # Check if the response contains tasks
        if "tasks" in response:
            print(f"Number of tasks: {len(response['tasks'])}")
            
            # Check if there are any tasks
            if len(response['tasks']) > 0:
                task = response['tasks'][0]
                
                # Print task ID and status
                print(f"Task ID: {task.get('id')}")
                print(f"Task Status: {task.get('status_code')} - {task.get('status_message')}")
                
                # Check if the task has results
                if "result" in task and task["result"] is not None:
                    print(f"Number of results: {len(task['result'])}")
                    
                    # Check if there are any results
                    if len(task['result']) > 0:
                        result = task['result'][0]
                        print(f"Result keys: {list(result.keys())}")
                        
                        # Check if the result has items
                        if "items" in result and result["items"] is not None:
                            print(f"Items type: {type(result['items'])}")
                            
                            # Handle different item structures
                            if isinstance(result["items"], dict):
                                print(f"Items keys: {list(result['items'].keys())}")
                                
                                # Check for organic results
                                if "organic" in result["items"] and result["items"]["organic"] is not None:
                                    organic_results = result["items"]["organic"]
                                    print(f"Number of organic results: {len(organic_results)}")
                                    
                                    # Print the first 3 organic results
                                    for i, item in enumerate(organic_results[:3], 1):
                                        print(f"\nOrganic Result {i}:")
                                        print(f"  URL: {item.get('url')}")
                                        print(f"  Title: {item.get('title')}")
                                        print(f"  Position: {item.get('position')}")
                                        print(f"  Rank Group: {item.get('rank_group')}")
                                        print(f"  Rank Absolute: {item.get('rank_absolute')}")
                                else:
                                    print("No organic results found in items dictionary")
                            elif isinstance(result["items"], list):
                                print(f"Items list length: {len(result['items'])}")
                                
                                # Check for organic items in the list
                                organic_results = []
                                for item in result["items"]:
                                    if isinstance(item, dict) and item.get("type") == "organic":
                                        organic_results.append(item)
                                
                                if organic_results:
                                    print(f"Number of organic results: {len(organic_results)}")
                                    
                                    # Print the first 3 organic results
                                    for i, item in enumerate(organic_results[:3], 1):
                                        print(f"\nOrganic Result {i}:")
                                        print(f"  URL: {item.get('url')}")
                                        print(f"  Title: {item.get('title')}")
                                        print(f"  Position: {item.get('position')}")
                                        print(f"  Rank Group: {item.get('rank_group')}")
                                        print(f"  Rank Absolute: {item.get('rank_absolute')}")
                                else:
                                    print("No organic results found in items list")
                            else:
                                print(f"Items is of unexpected type: {type(result['items'])}")
                        else:
                            print("No items found in result")
                    else:
                        print("No results found in task")
                else:
                    print("No result field in task or result is None")
            else:
                print("No tasks found in response")
        else:
            print("No tasks field in response")
        
        print("\nFull response saved to response.json")
        
    except Exception as e:
        print(f"Exception during API call: {e}")

if __name__ == "__main__":
    test_api()