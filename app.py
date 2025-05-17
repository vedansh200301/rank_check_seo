import os
import json
import tempfile
import csv
import io
import threading
import time
import shutil
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, Response, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename
from client import RestClient

# Import functions from rank_checker.py
from rank_checker import get_ranking

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)  # Enable CORS for all routes

# Create a templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

# Function to clean up old temporary files
def cleanup_old_files():
    """Clean up files in the uploads directory that are older than 24 hours"""
    try:
        uploads_dir = 'uploads'
        current_time = datetime.now()
        
        # Get all files in the uploads directory
        for filename in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
                
            # Get the file's modification time
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # If the file is older than 24 hours, delete it
            if current_time - file_mod_time > timedelta(hours=24):
                os.remove(file_path)
                print(f"Cleaned up old file: {file_path}")
    except Exception as e:
        print(f"Error cleaning up old files: {e}")

# Start a background thread to clean up old files periodically
def start_cleanup_thread():
    """Start a background thread to clean up old files every hour"""
    def cleanup_thread():
        while True:
            cleanup_old_files()
            time.sleep(3600)  # Sleep for 1 hour
    
    thread = threading.Thread(target=cleanup_thread)
    thread.daemon = True
    thread.start()

# Start the cleanup thread
start_cleanup_thread()

# Global variables to track processing status
processing_status = {
    'is_processing': False,
    'total_keywords': 0,
    'processed_keywords': 0,
    'current_keyword': '',
    'results': [],
    'error': None,
    'csv_file_path': None,
    'original_filename': None,
    'timestamp': int(time.time()),  # Add timestamp for cache busting
    'device': 'desktop',  # Default device
    'location_code': 2356,  # Default location code (India)
    'location_name': '',  # Default location name
    'session_id': ''  # Unique session identifier
}

@app.route('/', methods=['GET'])
def index():
    """Dashboard homepage"""
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    """Return the current processing status"""
    global processing_status
    
    # Get query parameters
    device = request.args.get('device')
    location_code = request.args.get('location_code')
    location_name = request.args.get('location_name')
    session_id = request.args.get('session_id')
    
    print(f"Status request received with parameters: device={device}, location_code={location_code}, location_name={location_name}, session_id={session_id}")
    print(f"Current processing status: {processing_status}")
    
    # Create a copy of the processing status
    status_copy = processing_status.copy()
    
    # Add a flag to indicate if the parameters match the current processing session
    if session_id:
        status_copy['parameters_match'] = (session_id == processing_status.get('session_id', ''))
        print(f"Session ID match: {status_copy['parameters_match']}")
    elif device or location_code or location_name:
        # For debugging
        print(f"Checking parameter match: frontend={device},{location_code},{location_name} vs backend={processing_status.get('device', '')},{processing_status.get('location_code', '')},{processing_status.get('location_name', '')}")
        
        # Always consider it a match if we're not currently processing
        if not processing_status['is_processing']:
            status_copy['parameters_match'] = True
            print("Not currently processing, so considering parameters to match")
        else:
            # Check if individual parameters match
            device_match = not device or device == processing_status.get('device', '')
            location_code_match = not location_code or location_code == str(processing_status.get('location_code', ''))
            location_name_match = not location_name or location_name == processing_status.get('location_name', '')
            status_copy['parameters_match'] = device_match and location_code_match and location_name_match
            print(f"Parameter matches: device={device_match}, location_code={location_code_match}, location_name={location_name_match}")
    else:
        # No parameters provided, assume match
        status_copy['parameters_match'] = True
        print("No parameters provided, assuming match")
    
    # Ensure results is always an array
    if 'results' in status_copy and status_copy['results'] is not None:
        print(f"Results count: {len(status_copy['results'])}")
    else:
        print("No results in status")
        status_copy['results'] = []
    
    # Add cache-busting headers
    response = jsonify(status_copy)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    print(f"Sending status response with {len(status_copy.get('results', []))} results")
    return response

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start processing"""
    global processing_status
    
    # Check if already processing
    if processing_status['is_processing']:
        return jsonify({"error": "Already processing a file. Please wait."}), 400
    
    # Reset status with new parameters
    current_timestamp = int(time.time())
    current_device = request.form.get('device', 'desktop')
    current_location_code = request.form.get('location_code', '2356')
    current_location_name = request.form.get('location_name', '')
    
    # Create a unique session ID
    device_hash = hashlib.md5(current_device.encode()).hexdigest()[:8]
    location_hash = hashlib.md5(f"{current_location_code}_{current_location_name}".encode()).hexdigest()[:8]
    session_id = f"{current_timestamp}_{device_hash}_{location_hash}"
    
    processing_status = {
        'is_processing': False,
        'total_keywords': 0,
        'processed_keywords': 0,
        'current_keyword': '',
        'results': [],  # Initialize as empty array
        'error': None,
        'csv_file_path': None,
        'original_filename': None,
        'timestamp': current_timestamp,
        'device': current_device,
        'location_code': current_location_code,
        'location_name': current_location_name,
        'session_id': session_id
    }
    
    # Get form data
    target_url = request.form.get('target_url')
    api_login = request.form.get('api_login')
    api_password = request.form.get('api_password')
    location_code = request.form.get('location_code', '2356')  # Default to India
    location_name = request.form.get('location_name', '')  # Optional city name
    device = request.form.get('device', 'desktop')  # Default to desktop
    limit = request.form.get('limit', '')
    
    # Validate required fields
    if not target_url or not api_login or not api_password:
        return jsonify({"error": "Missing required fields: target_url, api_login, api_password"}), 400
    
    # Check if file was uploaded
    if 'csv_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    csv_file = request.files['csv_file']
    if csv_file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Save the uploaded file with a unique name to prevent conflicts
    original_filename = secure_filename(csv_file.filename)
    
    # Create a unique identifier based on all parameters
    timestamp = int(time.time())
    device_hash = hashlib.md5(device.encode()).hexdigest()[:8]
    location_hash = hashlib.md5(f"{location_code}_{location_name}".encode()).hexdigest()[:8]
    
    # Create a unique filename that includes parameter hashes
    unique_filename = f"{timestamp}_{device_hash}_{location_hash}_{original_filename}"
    file_path = os.path.join('uploads', unique_filename)
    csv_file.save(file_path)
    
    # Store the original filename and parameters for display purposes
    processing_status['original_filename'] = original_filename
    processing_status['device'] = device
    processing_status['location_code'] = location_code
    processing_status['location_name'] = location_name
    processing_status['session_id'] = f"{timestamp}_{device_hash}_{location_hash}"
    
    # Convert limit to int if provided
    if limit and limit.isdigit():
        limit = int(limit)
    else:
        limit = None
    
    # Start processing in a background thread
    processing_status['is_processing'] = True
    processing_status['csv_file_path'] = file_path
    
    thread = threading.Thread(
        target=process_csv_file,
        args=(file_path, target_url, api_login, api_password, int(location_code), limit, location_name, device)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "File uploaded and processing started", "status_url": url_for('status')}), 200

@app.route('/download', methods=['GET'])
def download_file():
    """Download the processed CSV file"""
    global processing_status
    
    if not processing_status['csv_file_path'] or not os.path.exists(processing_status['csv_file_path']):
        return jsonify({"error": "No processed file available"}), 404
    
    try:
        # Use the original filename for the download if available, otherwise use the path basename
        filename = processing_status.get('original_filename') or os.path.basename(processing_status['csv_file_path'])
        
        # Read the file content into memory instead of creating a temporary file
        with open(processing_status['csv_file_path'], 'rb') as f:
            file_content = f.read()
        
        # Create a BytesIO object from the file content
        file_stream = io.BytesIO(file_content)
        file_stream.seek(0)
        
        # Set explicit headers for file download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'text/csv',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        
        # Return the file as a streaming response
        return Response(
            file_stream,
            mimetype='text/csv',
            headers=headers,
            direct_passthrough=True
        )
    except Exception as e:
        print(f"Error downloading file: {e}")
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 500

@app.route('/download-api/<file_id>', methods=['GET'])
def download_api_file(file_id):
    """Download a file by ID (filename)"""
    file_path = os.path.join('uploads', file_id)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        # Read the file content into memory
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Create a BytesIO object from the file content
        file_stream = io.BytesIO(file_content)
        file_stream.seek(0)
        
        # Use a more user-friendly filename if available
        global processing_status
        display_filename = processing_status.get('original_filename', file_id)
        
        # Set explicit headers for file download
        headers = {
            'Content-Disposition': f'attachment; filename="{display_filename}"',
            'Content-Type': 'text/csv',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Access-Control-Allow-Origin': '*'  # Allow cross-origin requests
        }
        
        # Return the file as a streaming response
        return Response(
            file_stream,
            mimetype='text/csv',
            headers=headers,
            direct_passthrough=True
        )
    except Exception as e:
        print(f"Error downloading API file: {e}")
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/check-rankings', methods=['POST'])
def check_rankings():
    """
    API endpoint to check rankings for keywords
    
    Expected JSON payload:
    {
        "target_url": "example.com",
        "api_credentials": {
            "login": "your_api_login",
            "password": "your_api_password"
        },
        "location_code": 2356,
        "location_name": "Mumbai",  // Optional city name
        "device": "desktop",        // desktop, mobile, or tablet
        "limit": 10,
        "keywords": ["keyword1", "keyword2", "keyword3"]
    }
    
    OR with CSV file upload:
    - Form data with 'csv_file' containing the CSV file
    - Form data with 'config' containing the JSON configuration
    """
    results = []
    
    # Check if this is a file upload or direct JSON payload
    if 'csv_file' in request.files:
        # Handle file upload
        csv_file = request.files['csv_file']
        config = json.loads(request.form.get('config', '{}'))
        
        if csv_file.filename == '':
            return jsonify({"error": "No file selected"}), 400
            
        # Save the uploaded file with a unique name to prevent conflicts
        original_filename = secure_filename(csv_file.filename)
        # Add timestamp to filename to make it unique
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{original_filename}"
        
        # Create uploads directory if it doesn't exist
        os.makedirs('uploads', exist_ok=True)
        
        # Save to uploads directory instead of a temporary directory
        file_path = os.path.join('uploads', unique_filename)
        csv_file.save(file_path)
        
        # Process the CSV file
        target_url = config.get('target_url')
        api_login = config.get('api_credentials', {}).get('login')
        api_password = config.get('api_credentials', {}).get('password')
        location_code = config.get('location_code', 2356)  # Default to India
        location_name = config.get('location_name', '')  # Optional city name
        device = config.get('device', 'desktop')  # Default to desktop
        limit = config.get('limit')
        
        if not target_url or not api_login or not api_password:
            return jsonify({"error": "Missing required parameters: target_url, api_login, api_password"}), 400
            
        # Initialize the API client
        client = RestClient(api_login, api_password)
        
        # Read keywords from CSV
        try:
            # Read the CSV file
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                # Check for keyword column
                keyword_column = None
                if rows and 'Keyword' in rows[0]:
                    keyword_column = 'Keyword'
                elif rows and 'Keywords' in rows[0]:
                    keyword_column = 'Keywords'
                else:
                    return jsonify({"error": "CSV must contain either a 'Keyword' or 'Keywords' column"}), 400
                
                # Get the header
                header = reader.fieldnames.copy() if reader.fieldnames else []
                
                # Check if ranking columns exist in the header, if not, add them
                ranking_columns = ['Ranking', 'Rank Group', 'Rank Absolute', 'Device']
                for column in ranking_columns:
                    if column not in header:
                        header.append(column)
                
                # Apply limit if specified
                if limit and limit < len(rows):
                    rows = rows[:limit]
                
                # Process each keyword
                for row in rows:
                    keyword = row[keyword_column]
                    print(f"Processing keyword: {keyword}")
                    
                    # Get ranking with geo_location parameter
                    ranking_info = get_ranking(client, keyword, target_url, location_code, location_name=location_name, device=device)
                    
                    # Store result
                    if isinstance(ranking_info, dict):
                        result = {
                            "keyword": keyword,
                            "ranking": ranking_info.get('position', 'N/A'),
                            "rank_group": ranking_info.get('rank_group', 'N/A'),
                            "rank_absolute": ranking_info.get('rank_absolute', 'N/A'),
                            "device": device
                        }
                        
                        # Update the row with ranking info
                        row['Ranking'] = ranking_info.get('position', 'N/A')
                        row['Rank Group'] = ranking_info.get('rank_group', 'N/A')
                        row['Rank Absolute'] = ranking_info.get('rank_absolute', 'N/A')
                        row['Device'] = device
                    else:
                        result = {
                            "keyword": keyword,
                            "ranking": ranking_info,
                            "rank_group": 'N/A',
                            "rank_absolute": 'N/A',
                            "device": device
                        }
                        
                        # Update the row with ranking info
                        row['Ranking'] = ranking_info
                        row['Rank Group'] = 'N/A'
                        row['Rank Absolute'] = 'N/A'
                        row['Device'] = device
                        
                    results.append(result)
                
                # Save the updated CSV
                with open(file_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(rows)
                
                # Read the updated CSV to return as response
                with open(file_path, 'r') as f:
                    csv_content = f.read()
                
                # Create a download URL for the file
                download_url = request.url_root.rstrip('/') + '/download-api/' + os.path.basename(file_path)
                
                # Don't remove the file yet, as it will be needed for download
                # We'll clean it up after download or after a timeout
                
                # Return JSON results, CSV content, and download URL
                return jsonify({
                    "results": results,
                    "csv_content": csv_content,
                    "download_url": download_url
                }), 200
                
        except Exception as e:
            return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500
            
    else:
        # Handle direct JSON payload
        data = request.json
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        target_url = data.get('target_url')
        api_login = data.get('api_credentials', {}).get('login')
        api_password = data.get('api_credentials', {}).get('password')
        location_code = data.get('location_code', 2356)  # Default to India
        location_name = data.get('location_name', '')  # Optional city name
        device = data.get('device', 'desktop')  # Default to desktop
        keywords = data.get('keywords', [])
        limit = data.get('limit')
        
        if not target_url or not api_login or not api_password:
            return jsonify({"error": "Missing required parameters: target_url, api_credentials"}), 400
            
        if not keywords:
            return jsonify({"error": "No keywords provided"}), 400
            
        # Apply limit if specified
        if limit and limit < len(keywords):
            keywords = keywords[:limit]
            
        # Initialize the API client
        client = RestClient(api_login, api_password)
        
        # Process each keyword
        for keyword in keywords:
            print(f"Processing keyword: {keyword}")
            
            # Get ranking with geo_location parameter
            ranking_info = get_ranking(client, keyword, target_url, location_code, location_name=location_name, device=device)
            
            # Store result
            if isinstance(ranking_info, dict):
                result = {
                    "keyword": keyword,
                    "ranking": ranking_info.get('position', 'N/A'),
                    "rank_group": ranking_info.get('rank_group', 'N/A'),
                    "rank_absolute": ranking_info.get('rank_absolute', 'N/A'),
                    "device": device
                }
            else:
                result = {
                    "keyword": keyword,
                    "ranking": ranking_info,
                    "rank_group": 'N/A',
                    "rank_absolute": 'N/A',
                    "device": device
                }
                
            results.append(result)
            
        return jsonify({"results": results}), 200

def process_csv_file(csv_file, target_url, api_login, api_password, location_code, limit=None, location_name='', device='desktop'):
    """Process the CSV file in the background"""
    global processing_status
    
    try:
        # Initialize the API client
        client = RestClient(api_login, api_password)
        
        # Read keywords from CSV
        keywords_data = []
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                keywords_data.append(row)
        
        # Apply limit if specified
        if limit and limit < len(keywords_data):
            keywords_data = keywords_data[:limit]
        
        # Update status
        processing_status['total_keywords'] = len(keywords_data)
        
        # Check for either 'Keyword' or 'Keywords' column
        if len(keywords_data) > 0:
            if 'Keyword' in keywords_data[0]:
                keyword_column = 'Keyword'
            elif 'Keywords' in keywords_data[0]:
                keyword_column = 'Keywords'
            else:
                processing_status['error'] = "CSV must contain either a 'Keyword' or 'Keywords' column."
                processing_status['is_processing'] = False
                return
        else:
            processing_status['error'] = "CSV file is empty."
            processing_status['is_processing'] = False
            return
        
        # Read the CSV file to get the structure
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
        
        # Create a ranking cache to avoid redundant API calls
        ranking_cache = {}
        
        # Process keywords in batches for better performance
        batch_size = 5  # Reduce batch size to 5 keywords to avoid timeouts
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
                
                # Update status
                processing_status['current_keyword'] = keyword
                processing_status['processed_keywords'] = current_index
                
                # Create a cache key
                cache_key = f"{keyword}_{target_url}_{location_code}_{location_name}_{device}"
                
                try:
                    # Check if we have a cached result
                    if cache_key in ranking_cache:
                        print(f"Using cached result for '{keyword}'")
                        ranking_info = ranking_cache[cache_key]
                    else:
                        # Pass location_name as geo_location parameter
                        print(f"Fetching ranking for '{keyword}' with location: {location_code}, location_name: {location_name}, device: {device}")
                        ranking_info = get_ranking(client, keyword, target_url, location_code, location_name=location_name, device=device)
                        # Cache the result
                        ranking_cache[cache_key] = ranking_info
                        
                        # Add a small delay between API calls within a batch
                        time.sleep(1)
                    
                    # Handle different types of ranking values
                    if isinstance(ranking_info, dict):
                        result = {
                            "keyword": keyword,
                            "ranking": ranking_info.get('position', 'N/A'),
                            "rank_group": ranking_info.get('rank_group', 'N/A'),
                            "rank_absolute": ranking_info.get('rank_absolute', 'N/A'),
                            "device": device
                        }
                        
                        # Update the row data
                        keyword_row['Ranking'] = ranking_info.get('position', 'N/A')
                        keyword_row['Rank Group'] = ranking_info.get('rank_group', 'N/A')
                        keyword_row['Rank Absolute'] = ranking_info.get('rank_absolute', 'N/A')
                        keyword_row['Device'] = device
                    else:
                        result = {
                            "keyword": keyword,
                            "ranking": ranking_info,
                            "rank_group": 'N/A',
                            "rank_absolute": 'N/A',
                            "device": device
                        }
                        
                        # Update the row data
                        keyword_row['Ranking'] = ranking_info
                        keyword_row['Rank Group'] = 'N/A'
                        keyword_row['Rank Absolute'] = 'N/A'
                        keyword_row['Device'] = device
                    
                    # Add to results
                    processing_status['results'].append(result)
                    
                    # Update the corresponding row in all_rows
                    for row in all_rows:
                        if row[keyword_column] == keyword:
                            row['Ranking'] = keyword_row['Ranking']
                            row['Rank Group'] = keyword_row['Rank Group']
                            row['Rank Absolute'] = keyword_row['Rank Absolute']
                            row['Device'] = device
                            break
                    
                except Exception as e:
                    processing_status['error'] = f"Error processing keyword '{keyword}': {str(e)}"
                    # Continue processing other keywords
                
                # Update the processed count after each keyword
                processing_status['processed_keywords'] = current_index + 1
            
            # Write the updated data back to the CSV file after processing the batch
            with open(csv_file, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=header)
                writer.writeheader()
                writer.writerows(all_rows)
            
            print(f"Updated CSV file with rankings for batch {batch_index + 1}/{total_batches}")
            
            # Add a longer delay between batches to avoid hitting API rate limits
            if batch_index < total_batches - 1:
                print(f"Waiting 5 seconds before processing next batch...")
                time.sleep(5)
        
        # Update final status
        processing_status['processed_keywords'] = processing_status['total_keywords']
        processing_status['current_keyword'] = 'Completed'
        print("Processing completed successfully!")
        print(f"Final results count: {len(processing_status.get('results', []))}")
        
        # Ensure results are properly set in the processing_status
        if not processing_status.get('results'):
            print("WARNING: No results found after processing. This is unexpected.")
            # Initialize results as empty array if it doesn't exist
            processing_status['results'] = []
        elif len(processing_status['results']) > 0:
            print(f"First result: {processing_status['results'][0]}")
        
    except Exception as e:
        processing_status['error'] = f"Error processing CSV file: {str(e)}"
        print(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Ensure is_processing is set to False
        processing_status['is_processing'] = False
        print(f"Final processing status: is_processing={processing_status['is_processing']}, total_keywords={processing_status['total_keywords']}, processed_keywords={processing_status['processed_keywords']}, results_count={len(processing_status.get('results', []))}")

if __name__ == '__main__':
    # Run the Flask app on port 5050
    app.run(host='127.0.0.1', port=5050, debug=True)