// DOM Elements
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const uploadBtn = document.getElementById('uploadBtn');
const ingestBtn = document.getElementById('ingestBtn');
const fileList = document.getElementById('fileList');
const statusMessage = document.getElementById('statusMessage');
const chatMessages = document.getElementById('chatMessages');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');

// State
let selectedFiles = [];
let isProcessingQuery = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkHealth();
});

// Setup Event Listeners
function setupEventListeners() {
    // File upload area click
    uploadArea.addEventListener('click', () => fileInput.click());
    
    // File selection
    fileInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    
    // Buttons
    uploadBtn.addEventListener('click', uploadFiles);
    ingestBtn.addEventListener('click', ingestDocuments);
    sendBtn.addEventListener('click', sendQuery);
    
    // Enter key to send
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isProcessingQuery) {
            sendQuery();
        }
    });
}

// Check API Health
async function checkHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();
        if (data.status === 'ok') {
            showStatus('API is running and ready! 🟢', 'success');
        }
    } catch (error) {
        showStatus('Unable to connect to API', 'error');
    }
}

// Handle File Selection
function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    addFilesToList(files);
}

// Handle Drag Over
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
}

// Handle Drag Leave
function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
}

// Handle Drop
function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    addFilesToList(files);
}

// Add Files to List
function addFilesToList(files) {
    // Filter for supported file types
    const supportedTypes = [
        // Documents
        '.pdf', '.docx', '.doc', '.odt', '.txt', '.md', '.rst', '.rtf',
        // Presentations & Spreadsheets
        '.pptx', '.xlsx', '.csv',
        // Data & Web
        '.json', '.xml', '.html', '.htm',
        // Code files
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', 
        '.go', '.rs', '.php', '.rb', '.swift', '.kt',
        // eBooks
        '.epub'
    ];
    const validFiles = files.filter(file => {
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        return supportedTypes.includes(ext);
    });
    
    if (validFiles.length === 0) {
        showStatus('Please select valid file types. See supported formats in the guide.', 'error');
        return;
    }
    
    selectedFiles = [...selectedFiles, ...validFiles];
    updateFileList();
    showStatus(`${validFiles.length} file(s) selected`, 'info');
}

// Update File List Display
function updateFileList() {
    fileList.innerHTML = '';
    selectedFiles.forEach((file, index) => {
        const li = document.createElement('li');
        li.textContent = file.name;
        fileList.appendChild(li);
    });
}

// Upload Files
async function uploadFiles() {
    if (selectedFiles.length === 0) {
        showStatus('Please select files first', 'error');
        return;
    }
    
    const formData = new FormData();
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });
    
    uploadBtn.disabled = true;
    showStatus('Uploading files...', 'info');
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showStatus(data.message + ' ✅', 'success');
            selectedFiles = [];
            updateFileList();
            fileInput.value = '';
        } else {
            showStatus('Upload failed: ' + data.detail, 'error');
        }
    } catch (error) {
        showStatus('Upload error: ' + error.message, 'error');
    } finally {
        uploadBtn.disabled = false;
    }
}

// Ingest Documents
async function ingestDocuments() {
    ingestBtn.disabled = true;
    
    try {
        // Start ingestion
        const response = await fetch('/ingest', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'processing') {
            // Start polling for status
            pollIngestionStatus();
        } else {
            showStatus('Failed to start processing: ' + (data.message || 'Unknown error'), 'error');
            ingestBtn.disabled = false;
        }
    } catch (error) {
        showStatus('Processing error: ' + error.message, 'error');
        ingestBtn.disabled = false;
    }
}

// Poll ingestion status
let statusPollInterval = null;

async function pollIngestionStatus() {
    // Clear any existing interval
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
    
    // Create or show progress bar
    showProgressBar();
    
    // Poll every 500ms
    statusPollInterval = setInterval(async () => {
        try {
            const response = await fetch('/ingest/status');
            const status = await response.json();
            
            // Update progress bar
            updateProgressBar(status.progress, status.message);
            
            // Check if completed or error
            if (status.status === 'completed') {
                clearInterval(statusPollInterval);
                statusPollInterval = null;
                hideProgressBar();
                showStatus(status.message + ' ✅', 'success');
                ingestBtn.disabled = false;
                
                // Enable chat interface
                queryInput.disabled = false;
                sendBtn.disabled = false;
                
                // Clear welcome message and add ready message
                const welcomeMsg = chatMessages.querySelector('.welcome-message');
                if (welcomeMsg) {
                    welcomeMsg.remove();
                }
                
                addBotMessage('Documents processed successfully! You can now ask me questions. 🤖');
            } else if (status.status === 'error') {
                clearInterval(statusPollInterval);
                statusPollInterval = null;
                hideProgressBar();
                showStatus('Processing failed: ' + (status.error || status.message), 'error');
                ingestBtn.disabled = false;
            }
        } catch (error) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
            hideProgressBar();
            showStatus('Status check error: ' + error.message, 'error');
            ingestBtn.disabled = false;
        }
    }, 500);
}

// Show progress bar
function showProgressBar() {
    let progressContainer = document.getElementById('progressContainer');
    
    if (!progressContainer) {
        // Create progress bar
        progressContainer = document.createElement('div');
        progressContainer.id = 'progressContainer';
        progressContainer.className = 'progress-container';
        progressContainer.innerHTML = `
            <div class="progress-label">Processing documents...</div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="progressBarFill" style="width: 0%"></div>
            </div>
            <div class="progress-percentage" id="progressPercentage">0%</div>
        `;
        
        // Insert after ingest button
        ingestBtn.parentNode.insertBefore(progressContainer, ingestBtn.nextSibling);
    }
    
    progressContainer.style.display = 'block';
}

// Update progress bar
function updateProgressBar(progress, message) {
    const progressBarFill = document.getElementById('progressBarFill');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressLabel = document.querySelector('.progress-label');
    
    if (progressBarFill && progressPercentage) {
        progressBarFill.style.width = progress + '%';
        progressPercentage.textContent = Math.round(progress) + '%';
        
        if (progressLabel && message) {
            progressLabel.textContent = message;
        }
    }
}

// Hide progress bar
function hideProgressBar() {
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 1000);
    }
}

// Send Query
async function sendQuery() {
    const query = queryInput.value.trim();
    
    if (!query || isProcessingQuery) {
        return;
    }
    
    // Add user message
    addUserMessage(query);
    queryInput.value = '';
    
    // Show loading
    const loadingId = addLoadingMessage();
    isProcessingQuery = true;
    sendBtn.disabled = true;
    queryInput.disabled = true;
    
    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });
        
        const data = await response.json();
        
        // Remove loading message
        removeLoadingMessage(loadingId);
        
        if (response.ok) {
            addBotMessage(data.response, data.sources);
        } else {
            addBotMessage('Sorry, I encountered an error: ' + data.detail);
        }
    } catch (error) {
        removeLoadingMessage(loadingId);
        addBotMessage('Sorry, I encountered an error: ' + error.message);
    } finally {
        isProcessingQuery = false;
        sendBtn.disabled = false;
        queryInput.disabled = false;
        queryInput.focus();
    }
}

// Add User Message
function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-user';
    messageDiv.innerHTML = `
        <div class="message-content">
            ${escapeHtml(text)}
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add Bot Message
function addBotMessage(text, sources = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';
    
    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `
            <div class="message-sources">
                <h4>📚 Sources:</h4>
                ${sources.map(source => `
                    <div class="source-item">
                        <span class="source-file">📄 ${escapeHtml(source.file)}</span>
                        <span class="source-text">${escapeHtml(truncateText(source.text, 150))}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            ${escapeHtml(text)}
            ${sourcesHtml}
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add Loading Message
function addLoadingMessage() {
    const loadingId = 'loading-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';
    messageDiv.id = loadingId;
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-loading">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return loadingId;
}

// Remove Loading Message
function removeLoadingMessage(loadingId) {
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
        loadingElement.remove();
    }
}

// Show Status Message
function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = 'status-message ' + type;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (statusMessage.textContent === message) {
            statusMessage.className = 'status-message';
        }
    }, 5000);
}

// Utility Functions
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

