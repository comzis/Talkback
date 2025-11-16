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
    checkLLMStatus();
    loadServerFiles(); // Load files from server on startup
    checkIndexStatus(); // Check if index exists and enable chat if ready
    
    // Periodically check status (every 30 seconds)
    setInterval(() => {
        checkHealth();
        checkLLMStatus();
    }, 30000);
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
        const apiStatusDot = document.getElementById('apiStatusDot');
        if (data.status === 'ok') {
            apiStatusDot.className = 'status-dot online';
            apiStatusDot.title = 'API Server is online';
        } else {
            apiStatusDot.className = 'status-dot warning';
            apiStatusDot.title = 'API Server has issues';
        }
    } catch (error) {
        const apiStatusDot = document.getElementById('apiStatusDot');
        apiStatusDot.className = 'status-dot';
        apiStatusDot.title = 'API Server is offline';
    }
}

// Check LLM Status
async function checkLLMStatus() {
    try {
        const response = await fetch('/llm/status');
        const data = await response.json();
        const llmStatusDot = document.getElementById('llmStatusDot');
        
        if (data.available && data.status === 'online') {
            if (data.model_available) {
                llmStatusDot.className = 'status-dot online';
                llmStatusDot.title = `LLM is online (${data.model_configured})`;
            } else {
                llmStatusDot.className = 'status-dot warning';
                llmStatusDot.title = `LLM is online but model '${data.model_configured}' not found. Available: ${data.models_installed.join(', ') || 'none'}`;
            }
        } else {
            llmStatusDot.className = 'status-dot';
            llmStatusDot.title = `LLM is offline: ${data.error || 'Unknown error'}`;
        }
    } catch (error) {
        const llmStatusDot = document.getElementById('llmStatusDot');
        llmStatusDot.className = 'status-dot';
        llmStatusDot.title = 'LLM status check failed';
    }
}

// Get file icon based on type (SF Symbols style SVG)
function getFileIcon(fileType, extension) {
    const icons = {
        'document': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>',
        'code': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>',
        'data': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>',
        'image': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
        'other': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>'
    };
    return icons[fileType] || icons['other'];
}

// Load files from server
async function loadServerFiles() {
    try {
        const response = await fetch('/files');
        const data = await response.json();
        
        if (data.files && data.files.length > 0) {
            updateServerFileList(data.files, data.by_type);
        } else {
            fileList.innerHTML = '<li style="color: var(--text-secondary); font-style: italic; padding: 20px; text-align: center;">No files uploaded yet</li>';
            updateFileStats({});
        }
    } catch (error) {
        console.error('Error loading server files:', error);
        // Don't show error to user, just log it
    }
}

// Update file statistics display
function updateFileStats(byType) {
    const fileStats = document.getElementById('fileStats');
    if (!byType || Object.keys(byType).length === 0) {
        fileStats.innerHTML = '';
        return;
    }
    
    const stats = [];
    if (byType.document > 0) stats.push(`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg> ${byType.document}`);
    if (byType.code > 0) stats.push(`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle;"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg> ${byType.code}`);
    if (byType.data > 0) stats.push(`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg> ${byType.data}`);
    if (byType.image > 0) stats.push(`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg> ${byType.image}`);
    if (byType.other > 0) stats.push(`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg> ${byType.other}`);
    
    fileStats.innerHTML = stats.map(stat => 
        `<span class="file-stat-item">${stat}</span>`
    ).join('');
}

// Update server file list display
function updateServerFileList(files, byType) {
    fileList.innerHTML = '';
    
    // Update statistics
    updateFileStats(byType);
    
    // Group files by type for better organization
    const filesByType = {};
    files.forEach(file => {
        if (!filesByType[file.type]) {
            filesByType[file.type] = [];
        }
        filesByType[file.type].push(file);
    });
    
    // Display files grouped by type
    const typeOrder = ['document', 'code', 'data', 'image', 'other'];
    typeOrder.forEach(type => {
        if (filesByType[type] && filesByType[type].length > 0) {
            filesByType[type].forEach(file => {
                const li = document.createElement('li');
                const icon = getFileIcon(file.type, file.extension);
                li.innerHTML = `
                    <span class="file-icon">${icon}</span>
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(file.filename || file.name)}</div>
                        <div class="file-meta">
                            <span class="file-type-badge ${file.type}">${file.type}</span>
                            <span>${formatFileSize(file.size)}</span>
                        </div>
                    </div>
                `;
                // Add smooth entrance animation
                li.style.opacity = '0';
                li.style.transform = 'translateY(8px)';
                fileList.appendChild(li);
                // Trigger animation
                requestAnimationFrame(() => {
                    li.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
                    li.style.opacity = '1';
                    li.style.transform = 'translateY(0)';
                });
            });
        }
    });
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Check if index exists and enable chat if ready
async function checkIndexStatus() {
    try {
        // Try a simple query to see if index exists
        // The backend will return a helpful message if no index
        // For now, just enable the chat - backend handles empty index gracefully
        queryInput.disabled = false;
        sendBtn.disabled = false;
        
        // Remove welcome message if chat is enabled
        const welcomeMsg = chatMessages.querySelector('.welcome-message');
        if (welcomeMsg) {
            welcomeMsg.innerHTML = `
                <h2>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle; margin-right: 8px;">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                    </svg>
                    Ready to chat!
                </h2>
                <p>You can ask questions now. If no documents are indexed yet, I'll let you know.</p>
                <p>Upload files and click "Process Documents" to index them for better answers.</p>
            `;
        }
    } catch (error) {
        console.error('Error checking index status:', error);
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
            // Reload server file list to show newly uploaded files
            setTimeout(() => loadServerFiles(), 500);
        } else {
            showStatus('Upload failed: ' + (data.detail || 'Unknown error'), 'error', true);
        }
    } catch (error) {
        showStatus('Upload error: ' + error.message, 'error', true);
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
            showStatus('Failed to start processing: ' + (data.message || 'Unknown error'), 'error', true);
            ingestBtn.disabled = false;
        }
    } catch (error) {
        showStatus('Processing error: ' + error.message, 'error', true);
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
                
                // Enable chat interface (should already be enabled, but ensure it)
                queryInput.disabled = false;
                sendBtn.disabled = false;
                
                // Clear welcome message and add ready message
                const welcomeMsg = chatMessages.querySelector('.welcome-message');
                if (welcomeMsg) {
                    welcomeMsg.remove();
                }
                
                addBotMessage('Documents processed successfully! You can now ask me questions.');
                
                // Reload server files to show current state
                loadServerFiles();
            } else if (status.status === 'error') {
                clearInterval(statusPollInterval);
                statusPollInterval = null;
                hideProgressBar();
                showStatus('Processing failed: ' + (status.error || status.message), 'error', true);
                ingestBtn.disabled = false;
                
                // Reload server files in case some were processed
                loadServerFiles();
            }
        } catch (error) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
            hideProgressBar();
            showStatus('Status check error: ' + error.message, 'error', true);
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
            addBotMessage('Sorry, I encountered an error: ' + (data.detail || 'Unknown error'));
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
    // Add smooth entrance animation
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(12px) scale(0.95)';
    chatMessages.appendChild(messageDiv);
    // Trigger animation
    requestAnimationFrame(() => {
        messageDiv.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0) scale(1)';
    });
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
                <h4>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle; margin-right: 6px;">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                    </svg>
                    Sources:
                </h4>
                ${sources.map(source => `
                    <div class="source-item">
                        <span class="source-file">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle; margin-right: 4px;">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                            </svg>
                            ${escapeHtml(source.file)}
                        </span>
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
    // Add smooth entrance animation
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(12px) scale(0.95)';
    chatMessages.appendChild(messageDiv);
    // Trigger animation
    requestAnimationFrame(() => {
        messageDiv.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0) scale(1)';
    });
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
function showStatus(message, type, persistent = false) {
    statusMessage.textContent = message;
    statusMessage.className = 'status-message ' + type;
    
    // Auto-hide after 5 seconds unless it's a persistent error
    if (!persistent) {
        setTimeout(() => {
            if (statusMessage.textContent === message) {
                statusMessage.className = 'status-message';
            }
        }, 5000);
    }
    // Persistent errors stay visible until user takes action or new status appears
}

// Utility Functions
function scrollToBottom() {
    // Smooth scroll with Apple-style easing
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
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

