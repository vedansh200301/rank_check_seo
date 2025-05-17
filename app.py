import os
import json
import tempfile
import csv
import io
import threading
import time
import shutil
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
    'csv_file_path': None
}

@app.route('/', methods=['GET'])
def index():
    """Dashboard homepage"""
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    """Return the current processing status"""
    global processing_status
    return jsonify(processing_status)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start processing"""
    global processing_status
    
    # Check if already processing
    if processing_status['is_processing']:
        return jsonify({"error": "Already processing a file. Please wait."}), 400
    
    # Reset status
    processing_status = {
        'is_processing': False,
        'total_keywords': 0,
        'processed_keywords': 0,
        'current_keyword': '',
        'results': [],
        'error': None,
        'csv_file_path': None
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
    
    # Save the uploaded file
    filename = secure_filename(csv_file.filename)
    file_path = os.path.join('uploads', filename)
    csv_file.save(file_path)
    
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
        # Get the original filename
        filename = os.path.basename(processing_status['csv_file_path'])
        
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
        
        # Set explicit headers for file download
        headers = {
            'Content-Disposition': f'attachment; filename="{file_id}"',
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
            
        # Save the uploaded file to a temporary location
        filename = secure_filename(csv_file.filename)
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
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
        
        # Process each keyword
        for i, keyword_row in enumerate(keywords_data):
            keyword = keyword_row[keyword_column]
            
            # Update status
            processing_status['current_keyword'] = keyword
            processing_status['processed_keywords'] = i
            
            # Get ranking
            try:
                # Pass location_name as geo_location parameter
                ranking_info = get_ranking(client, keyword, target_url, location_code, location_name=location_name, device=device)
                
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
                        break
                
                # Write the updated data back to the CSV file immediately
                with open(csv_file, 'w', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(all_rows)
                
            except Exception as e:
                processing_status['error'] = f"Error processing keyword '{keyword}': {str(e)}"
                # Continue processing other keywords
            
            # Add a small delay to avoid hitting API rate limits
            time.sleep(1)
        
        # Update final status
        processing_status['processed_keywords'] = processing_status['total_keywords']
        processing_status['current_keyword'] = 'Completed'
        
    except Exception as e:
        processing_status['error'] = f"Error processing CSV file: {str(e)}"
    
    finally:
        processing_status['is_processing'] = False

if __name__ == '__main__':
    # Run the Flask app on port 5050
    app.run(host='127.0.0.1', port=5050, debug=True)