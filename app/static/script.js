// Secure RAG Studio - JavaScript

// Superhero Persona - Sentinel Spark ⚡
const superheroPersona = {
    name: "Sentinel Spark",
    greetings: [
        "⚡ Sentinel Spark here! Your friendly neighborhood AI guardian, ready to protect your privacy and supercharge your knowledge!",
        "🦸 Greetings, citizen! Sentinel Spark reporting for duty. Let's unlock some insights together!",
        "⚡ *WHOOSH* Sentinel Spark has arrived! Time to make your documents work harder than a caffeinated squirrel!",
        "🦸 Hey there! Sentinel Spark at your service. I may not wear a cape, but I do wear encryption... which is basically the same thing!"
    ],
    jokes: [
        "Why did the AI go to therapy? It had too many deep learning issues! 😄",
        "I asked my neural network for a joke... it gave me a 404 error. Classic! 🤖",
        "What's an AI's favorite snack? Microchips! 🍟",
        "I'm not saying I'm fast, but I process information faster than you can say 'machine learning'! ⚡",
        "Why don't AIs ever get lost? Because they always follow the right path... or gradient! 🧭"
    ],
    references: [
        "With great processing power comes great responsibility! 🕷️",
        "I am... inevitable. (At least when it comes to finding answers in your docs!) 💎",
        "To infinity and beyond... your document collection! 🚀",
        "May the embeddings be with you! ⭐",
        "I could do this all day! (Processing documents, that is) 🛡️"
    ],
    encouragements: [
        "You're doing amazing! Even Tony Stark would be impressed! 🦾",
        "Keep going, hero! Your knowledge base is growing stronger! 💪",
        "Excellent question! You're leveling up faster than Spider-Man! 🕸️",
        "Wow! That's a great query. You're basically a superhero yourself! 🦸",
        "Fantastic work! You're assembling knowledge like the Avengers assemble! 🎯"
    ]
};

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
    uploadBtn: document.getElementById('uploadBtn'),
    processBtn: document.getElementById('processBtn'),
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadFiles();
    loadModels();
    startStatusMonitoring();
});

// Event Listeners
function initializeEventListeners() {
    // File upload
    elements.dropZone.addEventListener('click', () => elements.fileInput.click());
    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
    elements.dropZone.addEventListener('drop', handleDrop);
    elements.fileInput.addEventListener('change', handleFileSelect);
    
    // Buttons
    elements.uploadBtn.addEventListener('click', uploadFiles);
    elements.processBtn.addEventListener('click', processDocuments);
    elements.refreshBtn.addEventListener('click', refreshAll);
    elements.changeModelBtn.addEventListener('click', () => elements.modelModal.style.display = 'flex');
    elements.closeModal.addEventListener('click', () => elements.modelModal.style.display = 'none');
    elements.addModelBtn.addEventListener('click', addModel);
    
    // Monitoring
    elements.enableMonitoringBtn.addEventListener('click', enableMonitoring);
    
    // Chat
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
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
    const files = Array.from(e.dataTransfer.files);
    state.selectedFiles = files;
    updateQueue();
    showToast(`${files.length} file(s) ready to upload`, 'info');
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    state.selectedFiles = files;
    updateQueue();
    showToast(`${files.length} file(s) selected`, 'info');
}

// File Upload
async function uploadFiles() {
    if (state.selectedFiles.length === 0) {
        showToast('Please select files first', 'error');
        return;
    }
    
    const formData = new FormData();
    state.selectedFiles.forEach(file => formData.append('files', file));
    
    try {
        elements.uploadBtn.disabled = true;
        elements.uploadBtn.textContent = 'Uploading...';
        
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`Uploaded ${data.uploaded_count} file(s)`, 'success');
            state.selectedFiles = [];
            updateQueue();
            loadFiles();
        } else {
            showToast(data.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload error: ' + error.message, 'error');
    } finally {
        elements.uploadBtn.disabled = false;
        elements.uploadBtn.textContent = 'Upload Files';
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
        const value = parseInt(el.previousElementSibling.textContent);
        el.textContent = value > 0 ? 'Awaiting files' : 'Awaiting files';
    });
}

function updateQueue() {
    elements.queueCount.textContent = `${state.selectedFiles.length} selected`;
    
    if (state.selectedFiles.length === 0) {
        elements.queueList.innerHTML = '';
        return;
    }
    
    elements.queueList.innerHTML = state.selectedFiles.map(file => `
        <div class="queue-item">${file.name}</div>
    `).join('');
}

// Process Documents
async function processDocuments() {
    if (state.files.length === 0) {
        showToast('No files to process', 'error');
        return;
    }
    
    try {
        elements.processBtn.disabled = true;
        elements.processBtn.innerHTML = '<span>⚡</span> Processing...';
        elements.ingestionStatus.textContent = 'Processing...';
        setTrafficLight(elements.ingestionLight, 'orange');
        
        const response = await fetch('/ingest', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Documents processed successfully', 'success');
            elements.ingestionStatus.textContent = 'Ready';
            elements.chatStatus.textContent = 'Ready';
            setTrafficLight(elements.ingestionLight, 'green');
        } else {
            showToast(data.error || 'Processing failed', 'error');
            elements.ingestionStatus.textContent = 'Error';
            setTrafficLight(elements.ingestionLight, 'red');
        }
    } catch (error) {
        showToast('Processing error: ' + error.message, 'error');
        elements.ingestionStatus.textContent = 'Error';
        setTrafficLight(elements.ingestionLight, 'red');
    } finally {
        elements.processBtn.disabled = false;
        elements.processBtn.innerHTML = '<span>⚡</span> Process Library';
    }
}

// Chat
async function sendMessage() {
    const query = elements.chatInput.value.trim();
    if (!query) return;
    
    // Add user message
    addMessage(query, 'user');
    elements.chatInput.value = '';
    
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

// Superhero Persona Functions
function getRandomItem(array) {
    return array[Math.floor(Math.random() * array.length)];
}

function addSuperheroFlair(message) {
    // Add superhero greeting or encouragement randomly (20% chance)
    if (Math.random() < 0.2) {
        const flair = Math.random() < 0.5 
            ? getRandomItem(superheroPersona.encouragements)
            : getRandomItem(superheroPersona.references);
        return `${message}\n\n_${flair}_`;
    }
    return message;
}

function getSuperheroGreeting() {
    return getRandomItem(superheroPersona.greetings);
}

function getSuperheroJoke() {
    return getRandomItem(superheroPersona.jokes);
}

// Update Embedding Status
function updateEmbeddingStatus(status) {
    if (!status) return;
    
    state.embeddingProgress.current = status.current || 0;
    state.embeddingProgress.total = status.total || 0;
    state.embeddingProgress.isProcessing = status.status === 'processing';
    
    // Update status text
    if (status.status === 'processing') {
        elements.embeddingStatus.textContent = 'Processing';
        setTrafficLight(elements.embeddingLight, 'orange');
        
        // Update progress bar
        const progress = status.total > 0 ? (status.current / status.total) * 100 : 0;
        elements.embeddingProgress.style.width = `${progress}%`;
        elements.embeddingProgressText.textContent = `${status.current} / ${status.total} chunks`;
    } else if (status.status === 'completed') {
        elements.embeddingStatus.textContent = 'Completed';
        setTrafficLight(elements.embeddingLight, 'green');
        elements.embeddingProgress.style.width = '100%';
        elements.embeddingProgressText.textContent = `${status.total} / ${status.total} chunks`;
        
        // Reset after 3 seconds
        setTimeout(() => {
            elements.embeddingStatus.textContent = 'Idle';
            elements.embeddingProgress.style.width = '0%';
            elements.embeddingProgressText.textContent = '0 / 0 chunks';
        }, 3000);
    } else if (status.status === 'error') {
        elements.embeddingStatus.textContent = 'Error';
        setTrafficLight(elements.embeddingLight, 'red');
    } else {
        elements.embeddingStatus.textContent = 'Idle';
        setTrafficLight(elements.embeddingLight, 'green');
        elements.embeddingProgress.style.width = '0%';
        elements.embeddingProgressText.textContent = '0 / 0 chunks';
    }
}

// Mock CPU and Memory monitoring (in a real scenario, this would come from the backend)
function updateSystemResources() {
    if (state.embeddingProgress.isProcessing) {
        // Simulate higher usage during processing
        const cpu = (60 + Math.random() * 30).toFixed(1);
        const memory = (50 + Math.random() * 20).toFixed(1);
        elements.cpuUsage.textContent = `${cpu}%`;
        elements.memoryUsage.textContent = `${memory}%`;
    } else {
        // Idle usage
        const cpu = (5 + Math.random() * 15).toFixed(1);
        const memory = (20 + Math.random() * 10).toFixed(1);
        elements.cpuUsage.textContent = `${cpu}%`;
        elements.memoryUsage.textContent = `${memory}%`;
    }
}

function addMessage(text, role, isLoading = false, sources = []) {
    const messageId = `msg-${Date.now()}`;
    const avatar = role === 'user' ? 'U' : '⚡';  // Superhero icon for assistant
    
    // Remove ambient message if it exists
    const ambient = elements.chatMessages.querySelector('.ambient-message');
    if (ambient) ambient.remove();
    
    // Add superhero flair to assistant messages
    let finalText = text;
    if (role === 'assistant' && !isLoading) {
        finalText = addSuperheroFlair(text);
    }
    
    let sourcesHTML = '';
    if (sources && sources.length > 0) {
        sourcesHTML = `
            <div class="message-sources">
                <div class="sources-title">📚 Sources Referenced</div>
                ${sources.map((source, index) => `
                    <div class="source-item">
                        <div class="source-number">${index + 1}</div>
                        <div class="source-text">
                            <strong>${source.source || 'Unknown'}</strong>
                            ${source.text ? `<br><span style="font-size: 12px; color: rgba(255,255,255,0.5);">${source.text.substring(0, 150)}...</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    const messageHTML = `
        <div class="message ${role}" id="${messageId}">
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                ${isLoading ? '⚡ Sentinel Spark is analyzing...' : finalText}
                ${sourcesHTML}
            </div>
        </div>
    `;
    
    elements.chatMessages.insertAdjacentHTML('beforeend', messageHTML);
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
                `<option value="${model.name}">${model.name}</option>`
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
            showToast(data.error || 'Failed to add model', 'error');
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
    const project = elements.langsmithProject.value.trim() || 'Secure RAG Monitoring';
    
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
                showToast('✅ LangChain monitoring enabled!', 'success');
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
            showToast(data.error || 'Failed to configure monitoring', 'error');
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
            elements.chatStatus.textContent = count > 0 ? 'Ready' : 'Awaiting documents';
        } else {
            elements.dbStatus.textContent = 'Disconnected';
            elements.dbDetail.textContent = 'No connection';
            setTrafficLight(elements.dbLight, 'red');
        }
        
        // Ingestion Status
        setTrafficLight(elements.ingestionLight, 'green');
        
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
            elements.langsmithProject.value = data.monitoring.project || 'Secure RAG Monitoring';
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
    updateSystemResources();
    
    setInterval(checkSystemStatus, 5000);
    setInterval(checkIngestionStatus, 2000);  // Check embedding status more frequently
    setInterval(updateSystemResources, 1000);  // Update CPU/Memory every second
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
