// Secure RAG Studio - JavaScript

// State
const state = {
    files: [],
    selectedFiles: [],
    currentModel: null,
    fileTypes: {
        documents: 0,
        sheets: 0,
        slides: 0,
        data: 0,
        code: 0,
        ebooks: 0,
        images: 0,
        videos: 0,
        other: 0
    },
    embeddingProgress: {
        current: 0,
        total: 0,
        isProcessing: false
    }
};

// DOM Elements
const elements = {
    dropZone: document.getElementById('dropZone'),
    fileInput: document.getElementById('fileInput'),
    refreshBtn: document.getElementById('refreshBtn'),
    chatInput: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),
    chatMessages: document.getElementById('chatMessages'),
    queueList: document.getElementById('queueList'),
    queueCount: document.getElementById('queueCount'),
    docCount: document.getElementById('docCount'),
    changeModelBtn: document.getElementById('changeModelBtn'),
    modelModal: document.getElementById('modelModal'),
    closeModal: document.getElementById('closeModal'),
    modelSelect: document.getElementById('modelSelect'),
    addModelBtn: document.getElementById('addModelBtn'),
    newModelInput: document.getElementById('newModelInput'),
    toastContainer: document.getElementById('toastContainer'),
    // Status elements
    apiStatus: document.getElementById('apiStatus'),
    apiLight: document.getElementById('apiLight'),
    dbStatus: document.getElementById('dbStatus'),
    dbDetail: document.getElementById('dbDetail'),
    dbLight: document.getElementById('dbLight'),
    ingestionStatus: document.getElementById('ingestionStatus'),
    ingestionLight: document.getElementById('ingestionLight'),
    llmStatus: document.getElementById('llmStatus'),
    llmModel: document.getElementById('llmModel'),
    llmLight: document.getElementById('llmLight'),
    embeddingStatus: document.getElementById('embeddingStatus'),
    embeddingLight: document.getElementById('embeddingLight'),
    embeddingProgress: document.getElementById('embeddingProgress'),
    embeddingProgressText: document.getElementById('embeddingProgressText'),
    progressPercentage: document.getElementById('progressPercentage'),
    currentFileDisplay: document.getElementById('currentFileDisplay'),
    currentFileName: document.getElementById('currentFileName'),
    fileProgress: document.getElementById('fileProgress'),
    fileProgressText: document.getElementById('fileProgressText'),
    processingStats: document.getElementById('processingStats'),
    processingSpeed: document.getElementById('processingSpeed'),
    etaDisplay: document.getElementById('etaDisplay'),
    cpuUsage: document.getElementById('cpuUsage'),
    memoryUsage: document.getElementById('memoryUsage'),
    monitoringStatus: document.getElementById('monitoringStatus'),
    monitoringLight: document.getElementById('monitoringLight'),
    langsmithApiKey: document.getElementById('langsmithApiKey'),
    langsmithProject: document.getElementById('langsmithProject'),
    enableMonitoringBtn: document.getElementById('enableMonitoringBtn'),
    chatStatus: document.getElementById('chatStatus'),
    // File type stats
    docFiles: document.getElementById('docFiles'),
    sheetFiles: document.getElementById('sheetFiles'),
    slideFiles: document.getElementById('slideFiles'),
    dataFiles: document.getElementById('dataFiles'),
    codeFiles: document.getElementById('codeFiles'),
    imageFiles: document.getElementById('imageFiles'),
    videoFiles: document.getElementById('videoFiles')
};

function boot() {
    initializeEventListeners();
    loadFiles();
    loadModels();
    startStatusMonitoring();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
} else {
    boot();
}

// Event Listeners
function initializeEventListeners() {
    // File upload
    elements.dropZone.addEventListener('click', () => elements.fileInput.click());
    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
    elements.dropZone.addEventListener('drop', handleDrop);
    elements.fileInput.addEventListener('change', handleFileSelect);
    
    // Buttons
    elements.refreshBtn.addEventListener('click', refreshAll);
    elements.changeModelBtn.addEventListener('click', () => elements.modelModal.style.display = 'flex');
    elements.closeModal.addEventListener('click', () => elements.modelModal.style.display = 'none');
    elements.addModelBtn.addEventListener('click', addModel);
    
    // Monitoring
    elements.enableMonitoringBtn.addEventListener('click', enableMonitoring);
    
    // Chat
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    elements.chatInput.addEventListener('input', resizeChatInput);
    
    // Model
    elements.modelSelect.addEventListener('change', selectModel);
}

// Drag and Drop
function handleDragOver(e) {
    e.preventDefault();
    elements.dropZone.style.borderColor = 'var(--accent-blue)';
    elements.dropZone.style.background = 'rgba(10, 132, 255, 0.1)';
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.dropZone.style.borderColor = '';
    elements.dropZone.style.background = '';
}

function handleDrop(e) {
    e.preventDefault();
    elements.dropZone.style.borderColor = '';
    elements.dropZone.style.background = '';
    addFiles(Array.from(e.dataTransfer.files));
}

function handleFileSelect(e) {
    addFiles(Array.from(e.target.files));
    e.target.value = '';
}

async function addFiles(files) {
    if (!files || files.length === 0 || state.adding) return;

    state.adding = true;
    state.selectedFiles = files;
    updateQueue();

    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (response.ok) {
            const count = data.uploaded_count ?? files.length;
            showToast(`Added ${count} file(s). Indexing started.`, 'success');
            state.selectedFiles = [];
            updateQueue();
            loadFiles();
            checkIngestionStatus();
        } else {
            showToast(data.detail || data.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload error: ' + error.message, 'error');
    } finally {
        state.adding = false;
        updateQueue();
    }
}

// Load Files
async function loadFiles() {
    try {
        const response = await fetch('/files');
        const data = await response.json();
        
        state.files = data.files || [];
        categorizeFiles();
        updateFileStats();
        renderLibrary();
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function categorizeFiles() {
    state.fileTypes = {
        documents: 0,
        sheets: 0,
        slides: 0,
        data: 0,
        code: 0,
        ebooks: 0,
        images: 0,
        videos: 0,
        other: 0
    };
    
    state.files.forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        if (['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'].includes(ext)) {
            state.fileTypes.documents++;
        } else if (['xls', 'xlsx', 'csv'].includes(ext)) {
            state.fileTypes.sheets++;
        } else if (['ppt', 'pptx'].includes(ext)) {
            state.fileTypes.slides++;
        } else if (['json', 'xml', 'yaml'].includes(ext)) {
            state.fileTypes.data++;
        } else if (['py', 'js', 'ts', 'java', 'cpp', 'go', 'rs', 'rb', 'php'].includes(ext)) {
            state.fileTypes.code++;
        } else if (['epub', 'mobi'].includes(ext)) {
            state.fileTypes.ebooks++;
        } else if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp', 'ico', 'tiff', 'tif'].includes(ext)) {
            state.fileTypes.images++;
        } else if (['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v', 'mpg', 'mpeg'].includes(ext)) {
            state.fileTypes.videos++;
        } else {
            state.fileTypes.other++;
        }
    });
}

function updateFileStats() {
    elements.docCount.textContent = state.files.length;
    elements.docFiles.textContent = state.fileTypes.documents;
    elements.sheetFiles.textContent = state.fileTypes.sheets;
    elements.slideFiles.textContent = state.fileTypes.slides;
    elements.dataFiles.textContent = state.fileTypes.data;
    elements.codeFiles.textContent = state.fileTypes.code;
    elements.imageFiles.textContent = state.fileTypes.images;
    elements.videoFiles.textContent = state.fileTypes.videos;
    
    // Update sub-text
    document.querySelectorAll('.stat-sub').forEach(el => {
        const value = parseInt(el.previousElementSibling.textContent, 10);
        el.textContent = value > 0 ? 'Ready to process' : 'Awaiting files';
    });
}

function updateQueue() {
    const count = state.selectedFiles.length;
    elements.queueCount.textContent = state.adding ? `Adding ${count}` : 'Ready';
    elements.queueList.innerHTML = state.selectedFiles.map(file =>
        `<div class="queue-item">${escapeHtml(file.name)}</div>`
    ).join('');
}

// Chat
async function sendMessage() {
    const query = elements.chatInput.value.trim();
    if (!query) return;
    
    // Add user message
    addMessage(query, 'user');
    elements.chatInput.value = '';
    resizeChatInput();
    
    // Show loading
    const loadingId = addMessage('Thinking...', 'assistant', true);
    
    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        
        const data = await response.json();
        
        // Remove loading message
        removeMessage(loadingId);
        
        if (response.ok) {
            addMessage(data.response || data.answer, 'assistant', false, data.sources);
        } else {
            addMessage(data.detail || data.error || 'Query failed', 'assistant');
        }
    } catch (error) {
        removeMessage(loadingId);
        addMessage('Error: ' + error.message, 'assistant');
    }
}

function renderLibrary() {
    const list = document.getElementById('libraryList');
    if (!list) return;
    if (!state.files.length) {
        list.innerHTML = '';
        return;
    }
    list.innerHTML = state.files.map(file => {
        const name = file.filename || file.name;
        return `
            <div class="queue-item library-item">
                <span>${escapeHtml(name)}</span>
                <button type="button" class="delete-file" data-filename="${escapeHtml(name)}">Delete</button>
            </div>
        `;
    }).join('');
    list.querySelectorAll('.delete-file').forEach(button => {
        button.addEventListener('click', () => deleteLibraryFile(button.dataset.filename));
    });
}

async function deleteLibraryFile(name) {
    try {
        const response = await fetch('/files/' + encodeURIComponent(name), { method: 'DELETE' });
        const data = await response.json();
        if (response.ok) {
            showToast(`Deleted ${name}`, 'success');
            loadFiles();
        } else {
            showToast(data.detail || 'Delete failed', 'error');
        }
    } catch (error) {
        showToast('Delete error: ' + error.message, 'error');
    }
}

// Update Embedding Status
// Helper function to format seconds to human-readable time
function formatTime(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderEmbeddingBar(status) {
    const total = Number(status.total) || 0;
    const current = Number(status.current) || 0;
    const progress = Number.isFinite(status.progress)
        ? status.progress
        : (total > 0 ? (current / total) * 100 : 0);
    elements.embeddingProgress.style.width = `${progress}%`;
    elements.progressPercentage.textContent = `${Math.round(progress)}%`;
    elements.embeddingProgressText.textContent = `${current} / ${total} chunks`;
}

function updateEmbeddingStatus(status) {
    if (!status) return;
    if (status.status === 'processing') {
        elements.ingestionStatus.textContent = 'Processing';
        setTrafficLight(elements.ingestionLight, 'orange');
    } else if (status.status === 'error') {
        elements.ingestionStatus.textContent = 'Error';
        setTrafficLight(elements.ingestionLight, 'red');
    } else if (status.status === 'completed') {
        elements.ingestionStatus.textContent = 'Ready';
        setTrafficLight(elements.ingestionLight, 'green');
    }
    
    state.embeddingProgress.current = status.current || 0;
    state.embeddingProgress.total = status.total || 0;
    state.embeddingProgress.isProcessing = status.status === 'processing';
    
    // Update status text
    if (status.status === 'processing') {
        elements.embeddingStatus.textContent = 'Processing';
        setTrafficLight(elements.embeddingLight, 'orange');
        renderEmbeddingBar(status);
        
        // Add processing animation class
        elements.embeddingProgress.classList.add('processing');
        
        // Show and update current file display
        if (status.current_file) {
            elements.currentFileDisplay.style.display = 'flex';
            elements.currentFileName.textContent = status.current_file;
        } else {
            elements.currentFileDisplay.style.display = 'none';
        }
        
        // Show and update file progress
        if (status.total_files > 0) {
            elements.fileProgress.style.display = 'block';
            elements.fileProgressText.textContent = 
                `File ${status.processed_files + 1} of ${status.total_files}`;
        } else {
            elements.fileProgress.style.display = 'none';
        }
        
        // Show and update processing stats
        if (status.chunks_per_second > 0) {
            elements.processingStats.style.display = 'flex';
            elements.processingSpeed.textContent = 
                `${status.chunks_per_second.toFixed(1)} chunks/s`;
        } else {
            elements.processingStats.style.display = 'none';
        }
        
        // Show and update ETA
        if (status.estimated_time_remaining > 0) {
            elements.etaDisplay.textContent = formatTime(status.estimated_time_remaining);
        } else {
            elements.etaDisplay.textContent = '--';
        }
        
        // Update real CPU/Memory from backend
        if (status.cpu_percent !== undefined) {
            elements.cpuUsage.textContent = `${status.cpu_percent.toFixed(1)}%`;
        }
        if (status.memory_percent !== undefined) {
            elements.memoryUsage.textContent = `${status.memory_percent.toFixed(1)}%`;
        }
        
    } else if (status.status === 'completed') {
        elements.embeddingStatus.textContent = 'Completed';
        setTrafficLight(elements.embeddingLight, 'green');
        renderEmbeddingBar(status);
        
        // Remove processing animation
        elements.embeddingProgress.classList.remove('processing');
        
        // Hide extra elements
        elements.currentFileDisplay.style.display = 'none';
        elements.fileProgress.style.display = 'none';
        elements.processingStats.style.display = 'none';
        
        // Show final CPU/Memory if available
        if (status.cpu_percent !== undefined) {
            elements.cpuUsage.textContent = `${status.cpu_percent.toFixed(1)}%`;
        }
        if (status.memory_percent !== undefined) {
            elements.memoryUsage.textContent = `${status.memory_percent.toFixed(1)}%`;
        }
    } else if (status.status === 'error') {
        elements.embeddingStatus.textContent = 'Error';
        setTrafficLight(elements.embeddingLight, 'red');
        
        // Hide extra elements on error
        elements.currentFileDisplay.style.display = 'none';
        elements.fileProgress.style.display = 'none';
        elements.processingStats.style.display = 'none';
        elements.embeddingProgress.classList.remove('processing');
    } else {
        elements.embeddingStatus.textContent = 'Idle';
        setTrafficLight(elements.embeddingLight, 'green');
        renderEmbeddingBar(status);
        
        // Hide extra elements when idle
        elements.currentFileDisplay.style.display = 'none';
        elements.fileProgress.style.display = 'none';
        elements.processingStats.style.display = 'none';
        elements.embeddingProgress.classList.remove('processing');
    }
}

let messageSeq = 0;

function resizeChatInput() {
    const input = elements.chatInput;
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

function addMessage(text, role, isLoading = false, sources = []) {
    const messageId = `msg-${++messageSeq}`;
    const ambient = elements.chatMessages.querySelector('.ambient-message');
    if (ambient) ambient.remove();

    const message = document.createElement('div');
    message.className = `message ${role}`;
    message.id = messageId;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'A';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.textContent = isLoading ? 'Thinking...' : String(text ?? '').trim();

    if (sources && sources.length > 0) {
        const sourcesEl = document.createElement('div');
        sourcesEl.className = 'message-sources';
        const title = document.createElement('div');
        title.className = 'sources-title';
        title.textContent = 'Sources';
        sourcesEl.appendChild(title);
        sources.forEach((source, index) => {
            const item = document.createElement('div');
            item.className = 'source-item';
            const number = document.createElement('div');
            number.className = 'source-number';
            number.textContent = String(index + 1);
            const sourceText = document.createElement('div');
            sourceText.className = 'source-text';
            const name = document.createElement('strong');
            name.textContent = source.source || 'Unknown';
            sourceText.appendChild(name);
            if (source.text) {
                const excerpt = document.createElement('span');
                excerpt.textContent = ` ${source.text.substring(0, 150)}...`;
                sourceText.appendChild(excerpt);
            }
            item.append(number, sourceText);
            sourcesEl.appendChild(item);
        });
        content.appendChild(sourcesEl);
    }

    message.append(avatar, content);
    elements.chatMessages.appendChild(message);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return messageId;
}

function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) message.remove();
}

// Models
async function loadModels() {
    try {
        const response = await fetch('/llm/models');
        const data = await response.json();
        
        if (data.models && data.models.length > 0) {
            elements.modelSelect.innerHTML = data.models.map(model =>
                `<option value="${escapeHtml(model.name)}">${escapeHtml(model.name)}</option>`
            ).join('');
            
            if (data.current_model) {
                elements.modelSelect.value = data.current_model;
                state.currentModel = data.current_model;
            }
        } else {
            elements.modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

async function selectModel() {
    const model = elements.modelSelect.value;
    if (!model) return;
    
    try {
        const response = await fetch('/llm/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: model })
        });
        
        if (response.ok) {
            state.currentModel = model;
            elements.llmModel.textContent = `Ollama · ${model}`;
            elements.modelModal.style.display = 'none';
            showToast(`Model switched to ${model}`, 'success');
        } else {
            showToast('Failed to switch model', 'error');
        }
    } catch (error) {
        showToast('Error switching model', 'error');
    }
}

async function addModel() {
    const modelName = elements.newModelInput.value.trim();
    if (!modelName) {
        showToast('Please enter a model name', 'error');
        return;
    }
    
    try {
        elements.addModelBtn.disabled = true;
        elements.addModelBtn.textContent = 'Adding...';
        
        const response = await fetch('/llm/pull', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`Model ${modelName} added successfully`, 'success');
            elements.newModelInput.value = '';
            loadModels();
        } else {
            showToast(data.detail || data.error || 'Failed to add model', 'error');
        }
    } catch (error) {
        showToast('Error adding model', 'error');
    } finally {
        elements.addModelBtn.disabled = false;
        elements.addModelBtn.textContent = 'Add Model';
    }
}

// Monitoring
async function enableMonitoring() {
    const apiKey = elements.langsmithApiKey.value.trim();
    const project = elements.langsmithProject.value.trim() || 'Talkback';
    
    if (!apiKey && elements.monitoringStatus.textContent === 'Disabled') {
        showToast('Please enter your LangSmith API key', 'error');
        return;
    }
    
    try {
        elements.enableMonitoringBtn.disabled = true;
        elements.enableMonitoringBtn.textContent = 'Configuring...';
        
        const response = await fetch('/monitoring/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                api_key: apiKey,
                project: project,
                enabled: elements.monitoringStatus.textContent === 'Disabled'
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.enabled) {
                showToast('Monitoring enabled', 'success');
                elements.monitoringStatus.textContent = 'Enabled';
                setTrafficLight(elements.monitoringLight, 'green');
                elements.enableMonitoringBtn.textContent = 'Disable Monitoring';
            } else {
                showToast('Monitoring disabled', 'success');
                elements.monitoringStatus.textContent = 'Disabled';
                setTrafficLight(elements.monitoringLight, 'red');
                elements.enableMonitoringBtn.textContent = 'Enable Monitoring';
            }
        } else {
            showToast(data.detail || data.error || 'Failed to configure monitoring', 'error');
        }
    } catch (error) {
        showToast('Error configuring monitoring', 'error');
        console.error('Monitoring error:', error);
    } finally {
        elements.enableMonitoringBtn.disabled = false;
    }
}

// System Status
async function checkSystemStatus() {
    try {
        const response = await fetch('/system/status');
        const data = await response.json();
        
        // API Status
        if (data.api?.status === 'online') {
            elements.apiStatus.textContent = 'Online';
            setTrafficLight(elements.apiLight, 'green');
        } else {
            elements.apiStatus.textContent = 'Offline';
            setTrafficLight(elements.apiLight, 'red');
        }
        
        // Database Status
        if (data.database?.connected) {
            const count = data.database.collection_count || 0;
            elements.dbStatus.textContent = 'Connected';
            elements.dbDetail.textContent = `${count} documents`;
            setTrafficLight(elements.dbLight, 'green');
            elements.chatStatus.textContent = 'Talkback';
        } else {
            elements.dbStatus.textContent = 'Disconnected';
            elements.dbDetail.textContent = 'No connection';
            setTrafficLight(elements.dbLight, 'red');
        }
        
        // LLM Status
        if (data.llm?.available) {
            elements.llmStatus.textContent = 'Ready';
            elements.llmModel.textContent = `Ollama · ${data.llm.model_configured || 'llama3-8b'}`;
            setTrafficLight(elements.llmLight, 'green');
        } else {
            elements.llmStatus.textContent = 'Not loaded';
            setTrafficLight(elements.llmLight, 'red');
        }
        
        // Monitoring Status
        if (data.monitoring?.enabled) {
            elements.monitoringStatus.textContent = 'Enabled';
            setTrafficLight(elements.monitoringLight, 'green');
            elements.langsmithProject.value = data.monitoring.project || 'Talkback';
            elements.enableMonitoringBtn.textContent = 'Disable Monitoring';
        } else {
            elements.monitoringStatus.textContent = 'Disabled';
            setTrafficLight(elements.monitoringLight, 'red');
            elements.enableMonitoringBtn.textContent = 'Enable Monitoring';
        }
    } catch (error) {
        console.error('Error checking system status:', error);
        setTrafficLight(elements.apiLight, 'red');
        setTrafficLight(elements.dbLight, 'red');
        setTrafficLight(elements.llmLight, 'red');
    }
}

function setTrafficLight(element, color) {
    if (!element) return;
    element.className = `traffic-light ${color}`;
}

async function checkIngestionStatus() {
    try {
        const response = await fetch('/ingest/status');
        const data = await response.json();
        updateEmbeddingStatus(data);
    } catch (error) {
        console.error('Error checking ingestion status:', error);
    }
}

function startStatusMonitoring() {
    checkSystemStatus();
    checkIngestionStatus();
    
    setInterval(checkSystemStatus, 5000);
    setInterval(checkIngestionStatus, 2000);  // Check embedding status more frequently (now includes real CPU/Memory)
}

// Refresh All
async function refreshAll() {
    elements.refreshBtn.disabled = true;
    elements.refreshBtn.textContent = 'Refreshing...';
    
    await Promise.all([
        loadFiles(),
        loadModels(),
        checkSystemStatus()
    ]);
    
    elements.refreshBtn.disabled = false;
    elements.refreshBtn.textContent = 'Refresh';
    showToast('Refreshed', 'success');
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
`;
document.head.appendChild(style);
