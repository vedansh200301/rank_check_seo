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
            
            // Check status every 2 seconds
            statusCheckInterval = setInterval(checkStatus, 2000);
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
        
        // Set the iframe source to the download URL
        iframe.src = '/download';
        
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
        resultsBody.innerHTML = '';
    }
    
    // Check processing status
    function checkStatus() {
        fetch('/status')
        .then(response => response.json())
        .then(data => {
            // Update UI with status
            updateStatusUI(data);
            
            // Update progress
            updateProgressUI(data);
            
            // Update results table
            updateResultsTable(data.results);
        })
        .catch(error => {
            showError('Error checking status: ' + error.message);
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
        });
    }
    
    // Update status UI elements
    function updateStatusUI(data) {
        if (data.is_processing) {
            statusIndicator.className = 'status-indicator status-processing';
            statusText.textContent = 'Processing...';
        } else if (data.error) {
            statusIndicator.className = 'status-indicator status-error';
            statusText.textContent = 'Error';
            showError(data.error);
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
        } else if (data.processed_keywords >= data.total_keywords && data.total_keywords > 0) {
            statusIndicator.className = 'status-indicator status-completed';
            statusText.textContent = 'Completed';
            clearInterval(statusCheckInterval);
            submitBtn.disabled = false;
            downloadBtn.classList.remove('d-none');
        }
    }
    
    // Update progress UI elements
    function updateProgressUI(data) {
        currentKeyword.textContent = data.current_keyword || '-';
        
        if (data.total_keywords > 0) {
            const progress = Math.round((data.processed_keywords / data.total_keywords) * 100);
            progressText.textContent = `${data.processed_keywords}/${data.total_keywords}`;
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${progress}%`;
        }
    }
    
    // Update results table
    function updateResultsTable(results) {
        if (!results || results.length === 0) return;
        
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
            if (result.ranking === 1) {
                rankingCell.classList.add('text-success', 'fw-bold');
            } else if (result.ranking <= 10) {
                rankingCell.classList.add('text-primary');
            } else if (result.ranking === 'Error' || result.ranking === 'N/A') {
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