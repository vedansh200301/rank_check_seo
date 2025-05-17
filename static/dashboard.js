// Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const currentKeyword = document.getElementById('current-keyword');
    const progressText = document.getElementById('progress-text');
    const progressBar = document.getElementById('progress-bar');
    const errorMessage = document.getElementById('error-message');
    const downloadBtn = document.getElementById('download-btn');
    const resultsBody = document.getElementById('results-body');
    
    let statusCheckInterval;
    
    // Handle form field changes to reset UI
    const formFields = uploadForm.querySelectorAll('input, select');
    formFields.forEach(field => {
        field.addEventListener('change', function() {
            // Reset UI when any field changes
            resetUI();
        });
    });
    
    // Handle form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Reset UI
        resetUI();
        
        // Disable submit button
        submitBtn.disabled = true;
        
        // Create FormData object
        const formData = new FormData(uploadForm);
        
        // Send request
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
                return;
            }
            
            // Start checking status
            statusIndicator.classList.add('status-processing');
            statusText.textContent = 'Processing...';
            
            // Check status every 3 seconds (increased from 2 seconds)
            statusCheckInterval = setInterval(checkStatus, 3000);
        })
        .catch(error => {
            showError('Error uploading file: ' + error.message);
        });
    });
    
    // Handle download button click
    downloadBtn.addEventListener('click', function() {
        // Create a hidden iframe for downloading to avoid page navigation
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        
        // Set the iframe source to the download URL with cache busting
        const cacheBuster = new Date().getTime();
        iframe.src = `/download?_=${cacheBuster}`;
        
        // Remove the iframe after a short delay
        setTimeout(function() {
            document.body.removeChild(iframe);
        }, 5000);
        
        // Show a message to the user
        const downloadMessage = document.createElement('div');
        downloadMessage.className = 'alert alert-success';
        downloadMessage.textContent = 'Download started. If the file does not download automatically, please click the button again.';
        downloadMessage.style.marginTop = '10px';
        
        // Add the message after the download button
        downloadBtn.parentNode.appendChild(downloadMessage);
        
        // Remove the message after a few seconds
        setTimeout(function() {
            if (downloadMessage.parentNode) {
                downloadMessage.parentNode.removeChild(downloadMessage);
            }
        }, 5000);
    });
    
    // Reset UI elements
    function resetUI() {
        statusIndicator.className = 'status-indicator';
        statusText.textContent = 'Starting...';
        currentKeyword.textContent = '-';
        progressText.textContent = '0/0';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        errorMessage.classList.add('d-none');
        errorMessage.textContent = '';
        downloadBtn.classList.add('d-none');
        
        // Clear results table completely
        resultsBody.innerHTML = '';
        
        // Clear any previous download messages
        const downloadMessages = document.querySelectorAll('.alert');
        downloadMessages.forEach(msg => {
            if (msg.parentNode) {
                msg.parentNode.removeChild(msg);
            }
        });
    }
    
    // Check processing status
    function checkStatus() {
        // Get current form values
        const device = document.getElementById('device').value;
        const locationCode = document.getElementById('location-code').value;
        const locationName = document.getElementById('location-name').value;
        
        // Add cache-busting parameter to prevent caching
        const cacheBuster = new Date().getTime();
        
        console.log("Checking status with parameters:", {
            device,
            locationCode,
            locationName,
            cacheBuster
        });
        
        // Include current parameters in the status request
        fetch(`/status?_=${cacheBuster}&device=${encodeURIComponent(device)}&location_code=${encodeURIComponent(locationCode)}&location_name=${encodeURIComponent(locationName)}`)
        .then(response => response.json())
        .then(data => {
            console.log("Status response:", data);
            
            // Update UI with status
            updateStatusUI(data);
            
            // Update progress
            updateProgressUI(data);
            
            // Update results table with parameters_match flag
            if (data.results && data.results.length > 0) {
                console.log(`Updating results table with ${data.results.length} results`);
                updateResultsTable(data.results, data.parameters_match);
            } else {
                console.log("No results to display yet");
            }
            
            // If processing is complete, stop checking
            if (!data.is_processing && data.processed_keywords >= data.total_keywords && data.total_keywords > 0) {
                console.log("Processing complete, stopping status checks");
                clearInterval(statusCheckInterval);
                submitBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
            showError('Error checking status: ' + error.message);
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
        });
    }
    
    // Update status UI elements
    function updateStatusUI(data) {
        console.log("Updating status UI with:", {
            is_processing: data.is_processing,
            parameters_match: data.parameters_match,
            processed_keywords: data.processed_keywords,
            total_keywords: data.total_keywords,
            error: data.error
        });
        
        // Check if parameters match the current processing session
        if (data.parameters_match === false) {
            // Parameters don't match, show a warning and reset
            console.log("Parameters don't match, showing warning");
            statusIndicator.className = 'status-indicator status-warning';
            statusText.textContent = 'Parameters Changed';
            showError("Parameters have changed. Please submit the form again to process with new parameters.");
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
            return;
        }
        
        if (data.is_processing) {
            statusIndicator.className = 'status-indicator status-processing';
            statusText.textContent = 'Processing...';
        } else if (data.error) {
            console.log("Error detected:", data.error);
            statusIndicator.className = 'status-indicator status-error';
            statusText.textContent = 'Error';
            showError(data.error);
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
        } else if (data.processed_keywords >= data.total_keywords && data.total_keywords > 0) {
            console.log("Processing completed");
            statusIndicator.className = 'status-indicator status-completed';
            statusText.textContent = 'Completed';
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
            downloadBtn.classList.remove('d-none');
        } else {
            console.log("Status unclear:", data);
        }
    }
    
    // Update progress UI elements
    function updateProgressUI(data) {
        // Don't update progress if parameters don't match
        if (data.parameters_match === false) return;
        
        currentKeyword.textContent = data.current_keyword || '-';
        
        if (data.total_keywords > 0) {
            const progress = Math.round((data.processed_keywords / data.total_keywords) * 100);
            progressText.textContent = `${data.processed_keywords}/${data.total_keywords}`;
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${progress}%`;
        }
    }
    
    // Update results table
    function updateResultsTable(results, parametersMatch) {
        console.log("updateResultsTable called with:", {
            resultsType: results ? typeof results : 'undefined',
            resultsLength: results ? results.length : 0,
            parametersMatch: parametersMatch
        });
        
        // Don't update results if parameters don't match
        if (parametersMatch === false) {
            console.log("Parameters don't match, not updating results table");
            return;
        }
        
        // Handle case where results is undefined or empty
        if (!results) {
            console.log("Results is undefined or null");
            return;
        }
        
        if (!Array.isArray(results)) {
            console.log("Results is not an array, trying to convert");
            try {
                // Try to convert to array if it's not already
                results = Array.isArray(results) ? results : [results];
            } catch (e) {
                console.error("Failed to convert results to array:", e);
                return;
            }
        }
        
        if (results.length === 0) {
            console.log("Results array is empty");
            return;
        }
        
        console.log("Updating results table with", results.length, "results");
        console.log("First result:", JSON.stringify(results[0]));
        
        // Clear existing rows
        resultsBody.innerHTML = '';
        
        // Add new rows
        results.forEach(result => {
            const row = document.createElement('tr');
            
            const keywordCell = document.createElement('td');
            keywordCell.textContent = result.keyword;
            row.appendChild(keywordCell);
            
            const rankingCell = document.createElement('td');
            rankingCell.textContent = result.ranking;
            if (result.ranking === 1 || result.ranking === "1") {
                rankingCell.classList.add('text-success', 'fw-bold');
            } else if (parseInt(result.ranking) <= 10) {
                rankingCell.classList.add('text-primary');
            } else if (result.ranking === 'Error' || result.ranking === 'N/A' ||
                      result.ranking === 'API Error' || result.ranking === 'Not in top results') {
                rankingCell.classList.add('text-danger');
            }
            row.appendChild(rankingCell);
            
            const rankGroupCell = document.createElement('td');
            rankGroupCell.textContent = result.rank_group;
            row.appendChild(rankGroupCell);
            
            const rankAbsoluteCell = document.createElement('td');
            rankAbsoluteCell.textContent = result.rank_absolute;
            row.appendChild(rankAbsoluteCell);
            
            // Add device information
            const deviceCell = document.createElement('td');
            deviceCell.textContent = result.device || document.getElementById('device').value || 'desktop';
            row.appendChild(deviceCell);
            
            resultsBody.appendChild(row);
        });
    }
    
    // Show error message
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('d-none');
    }
});