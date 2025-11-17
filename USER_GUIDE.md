# Secure RAG Chatbot - User Guide

## Table of Contents
1. Overview
2. Prerequisites
3. Quick Start
4. Supported File Formats (30+)
5. Using the Chatbot Interface
6. API Endpoints (Advanced)
7. Example Workflows
8. Troubleshooting
9. System Architecture
10. Advanced Configuration

<hr />

## Overview

The Secure RAG (Retrieval-Augmented Generation) Chatbot is a privacy-focused system that allows you to:
- Chat with your documents using a beautiful web interface
- Upload files directly through your browser
- Get AI-generated responses with source citations
- Keep all data 100% local (no cloud services)

**Key Features:**
- 🔒 **100% Local Processing** - All data stays on your machine
- 💬 **Interactive Chatbot** - Modern web interface with Apple Liquid Glass design
- 📈 **LangChain Monitoring (optional)** - Stream ingest/query telemetry to LangSmith
- 📤 **Drag & Drop Upload** - Upload documents directly from your browser
- 📚 **30+ Document Formats** - Support for PDF, Word, Excel, PowerPoint, code files, eBooks, and more
- 🎯 **Source Citations** - Responses include references to source documents
- 💾 **Persistent Storage** - ChromaDB vector database with persistent storage
- 🤖 **Customizable LLM** - Use any Ollama-compatible model
- 💻 **Code Analysis** - Upload and query source code files
- 📊 **Data Processing** - Handle spreadsheets, CSV, JSON, and XML files
- 🎨 **Apple Design System** - Beautiful Liquid Glass UI with automatic dark mode support

---

## Prerequisites

Before starting, ensure you have:
- **Docker Desktop** installed and running
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **At least 8GB of RAM** available
- **5-10GB of free disk space** (for models and data)

---

## Quick Start

### Step 1: Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
# Required Environment Variables
OLLAMA_MODEL=gemma2:2b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

**Important:** 
- `OLLAMA_MODEL` - Specify your preferred Ollama model (default: `gemma2:2b` for optimal speed and privacy)
- `CHROMA_HOST` - Use `chromadb` for Docker networking
- `CHROMA_PORT` - Default ChromaDB port is `8000`

**Available Models:**
- `gemma2:2b` - Gemma 2 2B (very fast, 1.6 GB, **recommended default** ⚡)
- `llama2` - Llama 2 7B (good balance, 3.8 GB)
- `llama3` - Llama 3 8B (newer, better quality, 4.7 GB)
- `mistral` - Mistral 7B (high quality responses, 4.1 GB)
- `phi3` - Phi-3 Mini (efficient, good for limited resources, 2.3 GB)

### Step 2: Start the Services

```bash
# Build and start all services
docker compose up --build -d

# Check that all services are running
docker compose ps
```

You should see three services running:
- `chromadb_service` on port 8000
- `ollama_service` on port 11434
- `rag_api_service` on port 8001

### Step 3: Download the LLM Model

Before using the system, you need to download the LLM model:

```bash
# Download the default model (recommended - fast and efficient)
docker exec ollama_service ollama pull gemma2:2b

# Or use another model like:
# docker exec ollama_service ollama pull llama3
# docker exec ollama_service ollama pull llama2
# docker exec ollama_service ollama pull mistral
```

**Model Size & Performance Guide:**
- **gemma2:2b** (1.6 GB) - Very fast, privacy-focused ✅ **Default & Recommended**
- **llama2** (3.8 GB) - Balanced performance, good for most uses
- **llama3** (4.7 GB) - Better quality, slightly larger
- **mistral** (4.1 GB) - High quality responses
- **phi3** (2.3 GB) - Efficient, good quality for size

### Step 4: Open the Chatbot

Open your web browser and navigate to:

```
http://localhost:8001
```

You should see the Secure RAG Chatbot interface! 🎉

---

## 📁 Supported File Formats (30+)

The chatbot can process an extensive range of file formats, making it incredibly versatile for different use cases:

### 📄 Documents & Text
| Format | Extensions | Use Cases |
|--------|-----------|-----------|
| **PDF** | `.pdf` | Reports, papers, manuals, ebooks |
| **Microsoft Word** | `.docx`, `.doc` | Documents, proposals, contracts |
| **OpenDocument** | `.odt` | LibreOffice documents |
| **Plain Text** | `.txt` | Notes, logs, raw data |
| **Markdown** | `.md` | Documentation, README files |
| **reStructuredText** | `.rst` | Python documentation |
| **Rich Text** | `.rtf` | Formatted documents |

### 📊 Presentations & Spreadsheets
| Format | Extensions | Use Cases |
|--------|-----------|-----------|
| **PowerPoint** | `.pptx` | Presentations, slide decks |
| **Excel** | `.xlsx` | Spreadsheets, financial data |
| **CSV** | `.csv` | Data tables, exports |

### 🌐 Data & Web
| Format | Extensions | Use Cases |
|--------|-----------|-----------|
| **JSON** | `.json` | API responses, config files |
| **XML** | `.xml` | Structured data, configs |
| **HTML** | `.html`, `.htm` | Web pages, documentation |

### 💻 Source Code
| Format | Extensions | Use Cases |
|--------|-----------|-----------|
| **Python** | `.py` | Scripts, applications |
| **JavaScript/TypeScript** | `.js`, `.ts`, `.jsx`, `.tsx` | Web apps, Node.js |
| **Java** | `.java` | Enterprise applications |
| **C/C++** | `.c`, `.cpp`, `.h` | System programming |
| **Go** | `.go` | Backend services |
| **Rust** | `.rs` | Systems programming |
| **Other Languages** | `.php`, `.rb`, `.swift`, `.kt` | Various applications |

### 📚 eBooks
| Format | Extensions | Use Cases |
|--------|-----------|-----------|
| **EPUB** | `.epub` | Digital books, publications |

### 💡 Real-World Applications

**Documentation Hub:**
Upload your entire project documentation (README.md, API specs in JSON, PDFs, etc.) and ask questions across all documents.

**Code Review Assistant:**
Upload source code files and ask "What does this module do?" or "How is error handling implemented?"

**Business Intelligence:**
Upload Excel reports, CSV data, and PowerPoint presentations to query business metrics and insights.

**Research Assistant:**
Upload academic papers (PDF), research notes (DOCX), and data files (CSV) for comprehensive analysis.

**Learning Tool:**
Upload course materials, textbooks (EPUB), lecture slides (PPTX), and study notes to create your personal study assistant.

---

## Using the Chatbot Interface

### Overview

The chatbot interface features a modern **Apple Liquid Glass design** with:
- **Glassmorphism effects** - Translucent, frosted glass panels with backdrop blur
- **Automatic dark mode** - Adapts to your system preferences
- **Smooth animations** - Spring physics for natural interactions
- **SF Symbols icons** - Apple-style iconography throughout
- **San Francisco typography** - Native Apple font system
- **Live Pulse Metrics** - Real-time system status dashboard
- **LLM Model Management** - Select and switch between models dynamically
- **Enhanced File Display** - Beautiful file cards with type badges

The interface consists of:

1. **Header: Pulse Metrics Dashboard**
   - Live status cards with pulse animations
   - API Status (online/offline, response time)
   - LLM Status (model name, availability, response time)
   - Database Status (connection, collection count)
   - Alarms (error notifications, system alerts)
   - Updates every 3 seconds automatically

2. **Left Panel: Document Management & LLM Control**
   - **LLM Model Selector**: Dropdown to select from available models, add new models
   - **File Types Display**: Visual grid showing file counts by category
   - Glass-style file upload area (drag & drop or click)
   - Enhanced file cards with icons, names, sizes, and type badges
   - Process documents button with lightning icon
   - Status messages with glass effects

3. **Right Panel: Dynamic Chat Interface**
   - Glass-style chat history display
   - Message bubbles with glass effects and timestamps
   - Smooth message animations
   - Expandable source citations
   - Message input box with rounded design
   - Send button with smooth animations
   - Fully responsive for all screen sizes

### Step-by-Step Guide

#### 0. Monitor System Status

At the top of the interface, you'll see the **Pulse Metrics Dashboard** with live status cards:

- **API**: Shows if the API server is online
- **LLM**: Displays current model name, status, and response time
- **Database**: Shows ChromaDB connection status and collection count
- **Embeddings**: Real-time progress bar with current file, speed, ETA, CPU, and memory usage
- **LangChain Monitoring**: Optional telemetry tracking (enable with LangSmith API key)

These metrics update automatically every 2-5 seconds, giving you real-time visibility into your system's health.

#### 1. Select or Add LLM Model

The system defaults to **gemma2:2b** (fast, efficient, 1.6 GB). You can switch models anytime:

**Select Existing Model:**
1. In the System Pulse section, find the "LLM" card
2. Click the **"Change Model"** button
3. A modal will open showing all available models
4. Select your preferred model from the dropdown (e.g., `gemma2:2b`, `llama3:8b`, `llama2:latest`)
5. The system will switch immediately and close the modal
6. You'll see a success toast notification
7. The LLM card will update to show the new model (e.g., "Ollama · gemma2:2b")

**Add New Model:**
1. Click **"Change Model"** to open the modal
2. In the "Add Model" section, type the model name (e.g., `llama3`, `mistral`, `phi3`)
3. Click **"Add Model"** button
4. The system will start downloading the model in the background (this may take several minutes)
5. Check Docker logs to monitor download progress: `docker compose logs -f ollama`
6. Once downloaded, refresh the page and the model will appear in the dropdown

**Note:** Model switching happens instantly without restarting the service. The first query after switching may be slower as the new model loads into memory.

#### 2. View File Types

Above the upload area, you'll see a **File Types Grid** showing:
- Visual cards for each file category (Document, Code, Data, Image, Other)
- Count of files in each category
- Color-coded icons for easy identification
- Updates automatically when files are uploaded

This gives you a quick overview of what types of documents you have indexed.

#### 3. Upload Documents

**Method 1: Drag & Drop**
- Drag your files from your file explorer
- Drop them into the upload area
- Supports 30+ file formats including documents, code, data files, and more

**Method 2: Click to Browse**
- Click the upload area
- Select files from your computer
- Choose one or multiple files

**Supported Formats:**

**Documents:**
- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- OpenDocument (`.odt`)
- Plain Text (`.txt`)
- Markdown (`.md`)
- reStructuredText (`.rst`)
- Rich Text Format (`.rtf`)

**Presentations & Spreadsheets:**
- PowerPoint (`.pptx`)
- Excel (`.xlsx`)
- CSV (`.csv`)

**Data & Web:**
- JSON (`.json`)
- XML (`.xml`)
- HTML (`.html`, `.htm`)

**Source Code:**
- Python (`.py`)
- JavaScript/TypeScript (`.js`, `.ts`, `.jsx`, `.tsx`)
- Java (`.java`)
- C/C++ (`.c`, `.cpp`, `.h`)
- Go (`.go`)
- Rust (`.rs`)
- PHP, Ruby, Swift, Kotlin and more

**eBooks:**
- EPUB (`.epub`)

**Why So Many Formats?**
This makes the chatbot incredibly versatile:
- **Documentation**: Upload PDF manuals, Word docs, or Markdown READMEs
- **Code Analysis**: Upload your source code and ask questions about it
- **Data Exploration**: Upload CSV/JSON data files and query their contents
- **Research**: Upload EPUB books, HTML articles, or academic papers
- **Business**: Upload presentations, spreadsheets, and reports

#### 4. Upload Files to Server

After selecting files:
1. Click the **"Upload Files"** button (with upload icon)
2. Wait for the upload to complete
3. You'll see a success message with glass-style notification: "Successfully uploaded X file(s)"
4. Uploaded files will appear as **beautiful file cards** in a responsive grid:
   - Each card shows the file icon, name, type badge, and size
   - Cards are color-coded by file type
   - Smooth animations when files are added
   - Hover effects for better interactivity
5. The File Types Grid will update automatically to show new counts

#### 5. Process Documents

Once files are uploaded:
1. Click the **"Process Documents"** button (with lightning icon)
2. Watch the progress bar with glass-style design:
   - Progress percentage updates in real-time
   - Status messages show current processing stage
   - Smooth animations indicate activity
3. Watch the **Enhanced Embedding Status Bar** for detailed real-time feedback:
   - **Current File Display**: Shows which file is being processed (e.g., "Python_Basics.pdf")
   - **File Counter**: Displays progress like "File 2 of 5"
   - **Progress Bar**: Animated gradient with percentage inside (e.g., "45%")
   - **Processing Speed**: Real-time chunks/second (e.g., "12.5 chunks/s")
   - **Estimated Time**: Smart ETA (e.g., "2m 30s" or "45s")
   - **CPU Usage**: Live CPU percentage from your system
   - **Memory Usage**: Live memory percentage from your system
   - **Gradient Animation**: Progress bar flows through blue → purple → green with pulsing effect
4. Monitor the **Pulse Metrics Dashboard**:
   - Database status will update as collections are created
   - Traffic light indicators: 🟢 Green (ready), 🟠 Orange (processing), 🔴 Red (error)
5. Wait while the system:
   - Reads all documents from the data folder
   - Generates embeddings using AI (you'll see progress for each file)
   - Stores them in ChromaDB
6. You'll see: "Successfully ingested X chunks" with success notification
7. The embedding card will show completion with final stats (speed, CPU, memory)
8. The chat input will become active and ready for questions
9. The Database metric card will show the updated collection count

**Note:** Processing time depends on:
- Number of documents and chunks
- Size of documents
- Your computer's processing power (watch the real CPU/Memory metrics!)
- The embedding model's performance

#### 6. Ask Questions

Now you can chat with your documents:
1. Type your question in the rounded input box (glass-style design)
2. Press **Enter** or click the **Send button** (with send icon)
3. Watch smooth animations:
   - Your message slides in with spring physics
   - Message timestamp appears on hover
   - Loading dots appear while processing
   - Bot response animates in naturally
4. View the response with enhanced features:
   - Glass-style message bubbles with better spacing
   - Source documents listed with file icons
   - **Click on source items** to expand and see full text
   - Message timestamps for both user and bot messages
   - Smooth scrolling to new messages
5. Monitor the **LLM Status** card in the pulse metrics:
   - Response time updates after each query
   - Status changes if the model becomes unavailable

**Example Questions:**

**For PDFs & Documents:**
- "What are the main topics in these documents?"
- "Summarize the key points from the contract"
- "What does the document say about pricing?"

**For Code Files:**
- "Explain what this Python script does"
- "What are the main functions in this JavaScript file?"
- "How does the authentication system work?"

**For Spreadsheets & Data:**
- "What data is in the CSV file?"
- "Summarize the financial data from the Excel file"
- "What are the key metrics in the dataset?"

**For Presentations:**
- "Summarize the PowerPoint presentation"
- "What are the main points from slide 5?"
- "List all action items from the presentation"

**For Multiple Documents:**
- "Compare the approaches mentioned in these documents"
- "What are the common themes across all files?"
- "Find contradictions between document A and B"

#### 5. View Source Citations

Each response includes:
- **Main Answer:** AI-generated response with citation markers [1], [2], etc.
- **Sources Section:** Shows which documents were used
  - File name
  - Relevant text excerpt from that document

This allows you to:
- Verify the AI's answers
- Find the original source
- Understand the context

---

## API Endpoints (Advanced)

For developers who want to integrate with the system programmatically, the following REST API endpoints are available:

### Base URL
```
http://localhost:8001
```

### 1. Root - Chatbot Interface

**Endpoint:** `GET /`

**Description:** Serves the web-based chatbot interface.

**Example:**
```bash
# Open in browser
open http://localhost:8001
```

---

### 2. Health Check

**Endpoint:** `GET /health`

**Description:** Check if the API is running.

**Example:**
```bash
curl http://localhost:8001/health
```

**Response:**
```json
{
  "status": "ok"
}
```

---

### 2a. System Status (Comprehensive)

**Endpoint:** `GET /system/status`

**Description:** Get comprehensive system status including API, LLM, Database, and alarms.

**Example:**
```bash
curl http://localhost:8001/system/status
```

**Response:**
```json
{
  "timestamp": 1700000000.0,
  "api": {
    "status": "online",
    "uptime": "running"
  },
  "llm": {
    "status": "online",
    "available": true,
    "model_configured": "llama3:8b",
    "model_available": true,
    "response_time_ms": 45.2
  },
  "database": {
    "status": "online",
    "connected": true,
    "collection_count": 4778
  },
  "alarms": []
}
```

**Use Cases:**
- Monitor system health in real-time
- Check if all services are operational
- View current LLM model and response times
- Get notified of any system errors or warnings

---

### 2b. System Resources (Real-time Metrics)

**Endpoint:** `GET /system/resources`

**Description:** Get real-time CPU and memory usage from the system (powered by `psutil`).

**Example:**
```bash
curl http://localhost:8001/system/resources
```

**Response:**
```json
{
  "cpu_percent": 45.3,
  "memory_percent": 62.1,
  "timestamp": 1700000100.5
}
```

**Use Cases:**
- Monitor system resource usage in real-time
- Track CPU load during embedding or query operations
- Check memory consumption
- Build custom dashboards with system metrics

**Note:** This endpoint is used by the frontend to display real CPU/Memory metrics in the Embeddings status card.

---

### 2c. LLM Models Management

**List Models:**
**Endpoint:** `GET /llm/models`

**Description:** List all available Ollama models.

**Example:**
```bash
curl http://localhost:8001/llm/models
```

**Response:**
```json
{
  "models": [
    {
      "name": "llama3:8b",
      "size": 4700000000,
      "modified": "2024-01-01T00:00:00Z"
    },
    {
      "name": "mistral",
      "size": 4100000000,
      "modified": "2024-01-02T00:00:00Z"
    }
  ],
  "count": 2
}
```

**Select Model:**
**Endpoint:** `POST /llm/select`

**Description:** Switch to a different LLM model.

**Request Body:**
```json
{
  "model": "llama3:8b"
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/llm/select \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3:8b"}'
```

**Response:**
```json
{
  "message": "Successfully switched to model: llama3:8b",
  "model": "llama3:8b"
}
```

**Pull New Model:**
**Endpoint:** `POST /llm/pull`

**Description:** Download a new model from Ollama.

**Request Body:**
```json
{
  "model": "llama3"
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/llm/pull \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3"}'
```

**Response:**
```json
{
  "message": "Started pulling model: llama3",
  "model": "llama3",
  "status": "pulling"
}
```

**Note:** Model pulling happens in the background. Check Docker logs to see progress.

---

### 2c. File Types Statistics

**Endpoint:** `GET /files/types`

**Description:** Get file type statistics grouped by category.

**Example:**
```bash
curl http://localhost:8001/files/types
```

**Response:**
```json
{
  "by_type": {
    "document": {
      "count": 5,
      "total_size": 5242880,
      "files": [
        {
          "name": "report.pdf",
          "size": 1048576,
          "extension": ".pdf"
        }
      ]
    },
    "code": {
      "count": 3,
      "total_size": 1572864,
      "files": [...]
    }
  },
  "total_files": 11,
  "total_size": 10485760
}
```

---

### 3. Upload Files

**Endpoint:** `POST /upload`

**Description:** Upload one or more files to the server.

**Content-Type:** `multipart/form-data`

**Example (cURL):**
```bash
curl -X POST http://localhost:8001/upload \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx"
```

**Example (Python):**
```python
import requests

files = [
    ('files', open('document1.pdf', 'rb')),
    ('files', open('document2.docx', 'rb'))
]

response = requests.post('http://localhost:8001/upload', files=files)
print(response.json())
```

**Response (Success):**
```json
{
  "message": "Successfully uploaded 2 file(s).",
  "files": ["document1.pdf", "document2.docx"]
}
```

---

### 4. Ingest Documents

**Endpoint:** `POST /ingest`

**Description:** Process and index all documents from the data directory.

**Example (cURL):**
```bash
curl -X POST http://localhost:8001/ingest
```

**Example (Python):**
```python
import requests

response = requests.post('http://localhost:8001/ingest')
print(response.json())
```

**Response (Success):**
```json
{
  "message": "Successfully ingested 5 documents."
}
```

**Response (No Documents):**
```json
{
  "message": "No documents found to ingest."
}
```

**Note:** This endpoint runs as a background task. Use the `/ingest/status` endpoint (below) to monitor progress.

---

### 4a. Ingestion Status (Enhanced with Real-time Metrics)

**Endpoint:** `GET /ingest/status`

**Description:** Get detailed real-time status of document ingestion including file progress, processing speed, CPU/Memory usage, and ETA.

**Example:**
```bash
curl http://localhost:8001/ingest/status
```

**Response (Idle):**
```json
{
  "status": "idle",
  "progress": 0,
  "current": 0,
  "total": 0,
  "message": "",
  "error": null,
  "current_file": null,
  "total_files": 0,
  "processed_files": 0,
  "start_time": null,
  "chunks_per_second": 0.0,
  "cpu_percent": 0.0,
  "memory_percent": 0.0,
  "estimated_time_remaining": 0
}
```

**Response (Processing):**
```json
{
  "status": "processing",
  "progress": 45,
  "current": 150,
  "total": 335,
  "message": "Generating embeddings...",
  "error": null,
  "current_file": "Python_Basics.pdf",
  "total_files": 5,
  "processed_files": 2,
  "start_time": 1700000000.0,
  "chunks_per_second": 12.5,
  "cpu_percent": 65.2,
  "memory_percent": 58.3,
  "estimated_time_remaining": 150
}
```

**Response Fields:**
- `status`: `idle`, `processing`, `completed`, or `error`
- `current`: Current chunk being processed
- `total`: Total chunks to process
- `current_file`: Name of file currently being embedded (NEW in v2.5)
- `total_files`: Total number of files to process (NEW in v2.5)
- `processed_files`: Number of files completed (NEW in v2.5)
- `chunks_per_second`: Real-time processing speed (NEW in v2.5)
- `cpu_percent`: Real CPU usage from system (NEW in v2.5)
- `memory_percent`: Real memory usage from system (NEW in v2.5)
- `estimated_time_remaining`: ETA in seconds (NEW in v2.5)

**Use Cases:**
- Monitor embedding progress in real-time
- Display progress bars with accurate percentages
- Show current file being processed
- Calculate and display ETA to users
- Track system resource consumption during processing
- Build custom monitoring dashboards

---

### 5. Query Documents

**Endpoint:** `POST /query`

**Description:** Ask questions about your ingested documents and receive AI-generated answers with source citations.

**Request Body:**
```json
{
  "query": "Your question here"
}
```

**Example (cURL):**
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main topics discussed in the documents?"
  }'
```

**Example (Python):**
```python
import requests

response = requests.post(
    "http://localhost:8001/query",
    json={"query": "What are the main topics discussed in the documents?"}
)

result = response.json()
print("Response:", result["response"])
print("\nSources:")
for source in result["sources"]:
    print(f"- {source['file']}")
```

**Response:**
```json
{
  "response": "The main topics discussed include AI safety [1], machine learning applications [2], and data privacy concerns [1].",
  "sources": [
    {
      "file": "ai_safety_report.pdf",
      "text": "AI safety is crucial for ensuring that artificial intelligence systems are aligned with human values..."
    },
    {
      "file": "ml_applications.pdf",
      "text": "Machine learning has numerous applications in healthcare, finance, and autonomous systems..."
    }
  ]
}
```

**Response Fields:**
- `response` - The AI-generated answer with citation markers [1], [2], etc.
- `sources` - Array of source documents with relevant text chunks
  - `file` - Name of the source document
  - `text` - The specific text chunk that was referenced

---

## Example Workflows

### Workflow 1: First-Time Setup with Chatbot

```bash
# 1. Start Docker Desktop

# 2. Navigate to project directory
cd /path/to/secure-rag-project

# 3. Create .env file
cat > .env << EOF
OLLAMA_MODEL=gemma2:2b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# 4. Start services
docker compose up -d

# 5. Download the default model (fast and efficient)
docker exec ollama_service ollama pull gemma2:2b

# 6. Open browser
open http://localhost:8001

# 7. Use the web interface to:
#    - Upload documents (drag & drop - 30+ formats supported!)
#    - Click "Process Documents"
#    - Start chatting!
```

### Workflow 2: Using Existing Data Folder

If you already have documents in the `data/` folder:

```bash
# 1. Start services
docker compose up -d

# 2. Open browser
open http://localhost:8001

# 3. Click "Process Documents" (no upload needed)

# 4. Start asking questions!
```

### Workflow 3: Adding More Documents

To add more documents after initial setup:

```bash
# Option A: Use the web interface
# 1. Open http://localhost:8001
# 2. Drag & drop new files
# 3. Click "Upload Files"
# 4. Click "Process Documents" again

# Option B: Add to data folder manually
cp /path/to/new/documents/* data/

# Then in browser:
# 1. Open http://localhost:8001
# 2. Click "Process Documents"
```

### Workflow 4: Using a Different LLM Model

**Option A: Switch via Web UI (Recommended)**
```bash
# 1. Open browser
open http://localhost:8001

# 2. Click "Change Model" button in the LLM card
# 3. Select your preferred model from the dropdown
# 4. Model switches instantly - no restart needed!
```

**Option B: Change Default Model**
```bash
# 1. Update .env file with new model name
echo "OLLAMA_MODEL=llama3" > .env

# 2. Restart services
docker compose down
docker compose up -d

# 3. Download the new model if not already installed
docker exec ollama_service ollama pull llama3

# 4. Open browser and test
open http://localhost:8001
```

### Workflow 5: Programmatic Integration

Use the API endpoints for automation:

```python
import requests

# 1. Upload files
files = [('files', open('report.pdf', 'rb'))]
requests.post('http://localhost:8001/upload', files=files)

# 2. Process documents
requests.post('http://localhost:8001/ingest')

# 3. Query in a loop
questions = [
    "What is the executive summary?",
    "What are the key findings?",
    "What are the recommendations?"
]

for question in questions:
    response = requests.post(
        'http://localhost:8001/query',
        json={'query': question}
    )
    result = response.json()
    print(f"\nQ: {question}")
    print(f"A: {result['response']}")
```

### Workflow 6: Code Repository Analysis

Analyze a codebase by uploading source files:

```bash
# 1. Upload your code files (Python, JavaScript, Java, etc.)
# Upload via web interface: app.py, utils.py, config.js, etc.

# 2. Process the code files

# 3. Ask questions like:
# - "What does the authentication module do?"
# - "How is error handling implemented?"
# - "What are the main classes and their purposes?"
# - "Explain the database connection logic"
# - "What API endpoints are defined?"
```

### Workflow 7: Data File Analysis

Query spreadsheets and data files:

```bash
# 1. Upload data files (Excel, CSV, JSON, XML)
# Example: sales_data.xlsx, customer_info.csv, config.json

# 2. Process the files

# 3. Ask questions like:
# - "What is the total sales amount in the spreadsheet?"
# - "List all customers from the CSV file"
# - "What configuration settings are in the JSON?"
# - "Summarize the key metrics from the data"
```

### Workflow 8: Multi-Format Project Documentation

Combine different file types for comprehensive understanding:

```bash
# Upload a mix of formats:
# - README.md (project overview)
# - architecture.pdf (system design)
# - api_spec.json (API definitions)
# - setup.py, main.py (source code)
# - config.xml (configuration)
# - presentation.pptx (stakeholder slides)

# Then ask cross-document questions:
# - "What are the system requirements from the README and architecture docs?"
# - "How does the actual code in main.py align with the API spec?"
# - "What deployment steps are mentioned across all documents?"
```

---

## Troubleshooting

### Problem: Containers won't start

**Symptoms:**
```
Cannot connect to the Docker daemon
```

**Solution:**
- Ensure Docker Desktop is running
- Check Docker Desktop status in the menu bar (Mac) or system tray (Windows)
- Restart Docker Desktop if needed

---

### Problem: Browser shows "Cannot connect" or "ERR_CONNECTION_REFUSED"

**Symptoms:**
- Can't access http://localhost:8001
- Browser shows connection error

**Solutions:**

1. **Check if containers are running:**
   ```bash
   docker compose ps
   ```
   All three services should show "Up"

2. **Check API logs:**
   ```bash
   docker compose logs rag-api
   ```
   Look for: "Uvicorn running on http://0.0.0.0:8001"

3. **Restart services:**
   ```bash
   docker compose down
   docker compose up -d
   ```

---

### Problem: Missing environment variables error

**Symptoms:**
```
ValueError: Missing required environment variables:
  - OLLAMA_MODEL (LLM model name for Ollama)
```

**Solution:**
Create a `.env` file in the project root with all required variables:
```bash
OLLAMA_MODEL=llama2
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

---

### Problem: Model not found error (404)

**Symptoms:**
```
model 'model-name' not found (status code: 404)
```

**Solution:**
The model hasn't been downloaded yet. Download it first:

```bash
# Check what models you have
docker exec ollama_service ollama list

# Download the model specified in your .env file
docker exec ollama_service ollama pull llama2

# Then restart the API
docker compose restart rag-api
```

**Common Models to Download:**
```bash
# Default - Very fast, small size (1.6 GB) ⚡ RECOMMENDED
docker exec ollama_service ollama pull gemma2:2b

# Fast and balanced (3.8 GB)
docker exec ollama_service ollama pull llama2

# Better quality (4.7 GB)
docker exec ollama_service ollama pull llama3

# High quality (4.1 GB)
docker exec ollama_service ollama pull mistral
```

---

### Problem: "Upload Files" button doesn't work

**Symptoms:**
- Click upload but nothing happens
- Error message appears

**Solutions:**

1. **Check browser console** (F12 → Console tab)
   - Look for JavaScript errors

2. **Verify file formats:**
   - Only PDF, DOCX, TXT, MD are supported
   - Check file isn't corrupted

3. **Check file size:**
   - Very large files (>100MB) may timeout
   - Try splitting into smaller files

---

### Problem: "Process Documents" takes too long or times out

**Symptoms:**
- Processing hangs for minutes
- Timeout errors

**Possible Causes & Solutions:**

1. **Model not downloaded:**
   ```bash
   docker exec ollama_service ollama pull gemma2:2b
   ```

2. **Insufficient resources:**
   - Increase Docker Desktop memory allocation (Settings → Resources)
   - Close other applications to free up RAM
   - Try with fewer/smaller documents first

3. **Large document corpus:**
   - This is normal for first processing
   - Subsequent queries will be faster
   - Consider processing in batches

---

### Problem: Chat responses are slow

**Symptoms:**
- Queries take 30+ seconds
- Loading animation stays for long time

**Solutions:**

1. **First query is always slower** (model loading)
   - Wait for first query to complete
   - Subsequent queries will be faster

2. **Use a smaller model:**
   ```bash
   # Try a lighter model
   docker exec ollama_service ollama pull llama2:7b
   ```

3. **Reduce similarity_top_k** (see Advanced Configuration)

---

### Problem: No documents found during ingestion

**Symptoms:**
```json
{"message": "No documents found to ingest."}
```

**Solution:**

1. **If using web upload:**
   - Make sure you clicked "Upload Files" button
   - Check for success message before processing

2. **If using data folder:**
   ```bash
   # Verify files are present
   ls -la data/
   ```
   - Ensure files are supported formats
   - Ensure files are not empty

3. **Restart the RAG API service:**
   ```bash
   docker compose restart rag-api
   ```

---

### Problem: Responses say "context not helpful" or no sources

**Symptoms:**
- AI responds but says it can't find relevant information
- Sources array is empty

**Solutions:**

1. **Verify documents were ingested:**
   ```bash
   curl -X POST http://localhost:8001/ingest
   ```
   Should show "Successfully ingested X documents"

2. **Try more specific queries:**
   - Instead of: "Tell me about it"
   - Try: "What are the key features of the product?"

3. **Check if query matches document content:**
   - Documents must contain relevant information
   - Try asking about topics you know are in the documents

4. **Increase similarity_top_k** (see Advanced Configuration)

---

### Problem: File upload shows "no such service" or similar error

**Symptoms:**
- Upload endpoint returns 404 or 500 error

**Solution:**
```bash
# Rebuild containers with latest code
docker compose down
docker compose up --build -d
```

---

### Viewing Logs

Check logs for specific services:

```bash
# All services
docker compose logs -f

# RAG API only
docker compose logs -f rag-api

# ChromaDB only
docker compose logs -f chromadb

# Ollama only
docker compose logs -f ollama

# Last 50 lines from RAG API
docker compose logs --tail=50 rag-api
```

---

### Stopping and Cleaning Up

```bash
# Stop all services
docker compose down

# Stop and remove volumes (deletes all data)
docker compose down -v

# Remove all images
docker compose down --rmi all

# Full cleanup (removes everything)
docker compose down -v --rmi all
```

---

## System Architecture

### Services Overview

```
┌─────────────────────────────────────────────────────────┐
│                  User's Web Browser                     │
│              http://localhost:8001                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│         RAG API (FastAPI + LlamaIndex)                  │
│         Port: 8001                                      │
│  - Chatbot UI    - /upload    - /ingest    - /query   │
└────────┬──────────────────────────────┬─────────────────┘
         │                              │
         │ Vector Operations            │ LLM Requests
         ↓                              ↓
┌──────────────────────┐      ┌────────────────────────┐
│   ChromaDB           │      │   Ollama               │
│   Port: 8000         │      │   Port: 11434          │
│   (Vector Storage)   │      │   (Local LLM)          │
└──────────────────────┘      └────────────────────────┘
         │                              │
         ↓                              ↓
┌──────────────────────┐      ┌────────────────────────┐
│  ./chroma_data/      │      │  ollama_data volume    │
│  (Persistent)        │      │  (Models)              │
└──────────────────────┘      └────────────────────────┘
```

### Data Flow

1. **Upload Flow (Web Interface - 30+ Formats):**
   - User drags files to browser (PDF, Word, Excel, PowerPoint, code, data files, etc.)
   - JavaScript validates file types (30+ supported formats)
   - Files sent to `/upload` endpoint via multipart/form-data
   - FastAPI saves files to `/app/data/` directory

2. **Ingestion Flow:**
   - User clicks "Process Documents"
   - RAG API reads files from `/app/data/` (auto-detects format)
   - LlamaIndex parses each file using appropriate reader:
     * PDF → pypdf parser
     * Word → python-docx parser
     * Excel → openpyxl parser
     * PowerPoint → python-pptx parser
     * Code files → text reader
     * And more...
   - RAG API generates embeddings using HuggingFace model
   - Embeddings stored in ChromaDB
   - ChromaDB persists to `./chroma_data/`

3. **Query Flow:**
   - User types question and sends
   - RAG API generates query embedding
   - ChromaDB retrieves similar document chunks
   - Context + Query sent to Ollama LLM
   - LLM generates response with citations
   - Response returned to browser with sources

### Technology Stack

**Frontend:**
- HTML5, CSS3, JavaScript (Vanilla)
- **Apple Liquid Glass Design System** (2025)
- Glassmorphism with backdrop-filter blur effects
- San Francisco typography system
- SF Symbols iconography
- Automatic dark mode support
- Spring physics animations
- Responsive design with CSS Grid/Flexbox
- Drag & Drop File API
- Fetch API for HTTP requests

**Backend:**
- **FastAPI** - Modern Python web framework with multipart/form-data support
- **LlamaIndex** - RAG orchestration framework with 30+ file readers
- **ChromaDB** - Vector database for embeddings
- **Ollama** - Local LLM inference engine
- **File Parsers:**
  - pypdf (PDF), python-docx (Word), python-pptx (PowerPoint)
  - openpyxl (Excel), ebooklib (EPUB), lxml (XML)
  - beautifulsoup4 (HTML), and more
- **HuggingFace** - Embedding model (BAAI/bge-small-en-v1.5)
- **Docker** - Containerization and orchestration

---

## Advanced Configuration

### Customizing the Prompt Template

The system uses a custom prompt template to encourage citations. To modify it, edit `app/main.py`:

```python
qa_template = PromptTemplate(
    "Answer the user's question based only on the provided context.\n"
    "When you use information, you must cite the source using [source_number].\n"
    "For example: The sky is blue [1].\n"
    "If the context is not helpful, just say so.\n"
    "---------------------\n"
    "Context: {context_str}\n"
    "---------------------\n"
    "Question: {query_str}\n"
    "Answer: "
)
```

### Adjusting Retrieval Settings

Modify the number of document chunks retrieved per query in `app/main.py`:

```python
query_engine = CitationQueryEngine.from_args(
    index,
    similarity_top_k=3,  # Change this number (default: 3)
    citation_qa_template=qa_template,
)
```

- **Higher values (5-10)** = more context but slower responses
- **Lower values (1-2)** = faster but may miss relevant information

### Supported File Formats

The system supports **30+ file formats** out of the box:

**Document Formats:**
- PDF, Word (DOCX, DOC), OpenDocument (ODT)
- Plain Text (TXT), Markdown (MD), reStructuredText (RST), Rich Text (RTF)

**Office & Data:**
- PowerPoint (PPTX), Excel (XLSX), CSV
- JSON, XML, HTML

**Source Code:**
- Python, JavaScript/TypeScript, Java, C/C++, Go, Rust
- PHP, Ruby, Swift, Kotlin, and more

**eBooks:**
- EPUB

**Use Cases:**
1. **Technical Documentation**: Upload API docs, user manuals, or wikis
2. **Codebase Q&A**: Upload source code files and ask about functionality
3. **Data Analysis**: Upload CSV/Excel files and query the data
4. **Research Assistant**: Upload academic papers, articles, or books
5. **Business Intelligence**: Upload reports, presentations, or spreadsheets
6. **Learning**: Upload course materials, tutorials, or textbooks

**Adding More Formats:**
To add support for additional file types, you can:
1. Update the `accept` attribute in `/app/static/index.html`
2. Update the `supportedTypes` array in `/app/static/script.js`
3. Add required dependencies to `/app/requirements.txt` if needed

### Customizing the UI

The chatbot interface uses **Apple Liquid Glass Design System** and can be customized by editing:

**Colors and Styling:**
Edit `/app/static/style.css` and modify Apple system colors:
```css
:root {
    --system-blue: #007AFF;         /* Apple system blue */
    --system-green: #34C759;        /* Apple system green */
    --system-red: #FF3B30;          /* Apple system red */
    --glass-bg: rgba(255, 255, 255, 0.7);  /* Glass background */
    --glass-border: rgba(255, 255, 255, 0.18); /* Glass border */
}
```

**Dark Mode:**
The interface automatically adapts to your system's dark mode preference. To customize dark mode colors, edit the `@media (prefers-color-scheme: dark)` section in `style.css`.

**Glass Effects:**
Adjust glassmorphism intensity:
```css
backdrop-filter: blur(40px) saturate(180%);  /* Change blur/saturation */
```

**Behavior:**
Edit `/app/static/script.js` to modify:
- Auto-scroll behavior (smooth scrolling with spring physics)
- Loading animations (bounce effects)
- Status messages (glass-style notifications)
- File validation rules
- Message entrance animations

### Phase B: Upcoming UX Enhancements

To push the Apple-inspired identity even further, consider these next-wave ideas:

1. **Layout Modes**
   - **Compact Split View:** Collapse the sidebar into an icon rail for smaller breakpoints while keeping the chat full-height.
   - **Focus Canvas:** Dim the background and expand the chat bubble stack for presentation/demo scenarios.
   - **Dual-Pane Compare:** Allow users to pin a file preview or metric card next to the chat thread for side-by-side analysis.

2. **Micro-Interactions**
   - Introduce **haptic-friendly cues** (via the Web Vibration API) when uploads complete or when an alarm triggers.
   - Layer **subtle spatial audio** or chimes (SF system sounds) for send/receive events with a mute toggle in settings.
   - Add **gesture affordances** (swipe-to-close for sources, long-press on metric cards to expand details).

3. **Adaptive Pulse Metrics**
   - Animate radial progress rings around each metric card, syncing to response times.
   - Surface a mini timeline that shows API/LLM status changes over the past minute for quick debugging.

4. **Theme Variations**
   - Offer preset Apple palettes: **Sierra Mist**, **Monterey Twilight**, and **Night Shift** (warmer glass tints for evening work).
   - Add a **“Pro Display”** toggle that increases density, tightens typography, and reveals numerical diagnostics.

5. **Accessibility Extras**
   - Provide a **Reduce Transparency** toggle that swaps glass cards for solid surfaces.
   - Include a **High Contrast** overlay and color-blind friendly accents for each file type badge.

Documenting these concepts now keeps Phase B organized—each bullet points to a specific area in `style.css`, `index.html`, or `script.js` that can be extended without rewriting the current experience.

### LangChain Monitoring & LangSmith Integration

If you want full observability for ingest and query runs, you can enable the built-in LangChain/LangSmith monitoring hook:

1. **Install dependencies** – already included in `app/requirements.txt` (`langsmith>=0.1.28`). Rebuild the container if needed:  
   ```bash
   docker compose up --build rag-api
   ```
2. **Set environment variables** (you can reuse your LangSmith workspace keys):
   ```bash
   LANGCHAIN_MONITORING=true
   LANGCHAIN_PROJECT="Secure RAG Monitoring"
   LANGSMITH_API_KEY=ls__xxxxxxxxxxxxxxxx
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   ```
3. **What gets recorded**
   - `document_ingestion` runs capture document counts, status, and errors.
   - `rag_query` runs log the user query, completion status, and the files cited in the answer.
4. **Where to view data**
   - Visit the [LangSmith dashboard](https://smith.langchain.com/) and open the project you set in `LANGCHAIN_PROJECT`.
   - Each run is tagged (`ingestion`, `query`, `rag`) so you can filter quickly.

This mirrors the guidance at [LangChain Monitoring](https://python.langchain.com/docs/guides/tracing) and keeps all telemetry optional—if `LANGCHAIN_MONITORING` is not set to `true`, the app behaves exactly as before.

### Manual Smoke Test Checklist

After deploying, you can run a quick end-to-end verification directly from a terminal (or CI job):

```bash
# 1. API health
curl http://localhost:8001/health

# 2. System status (LLM + DB telemetry)
curl http://localhost:8001/system/status | jq

# 3. File-type stats (verifies ingestion metadata)
curl http://localhost:8001/files/types | jq '.total_files'

# 4. Sample RAG query (ensures embeddings + LLM path)
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize available documents"}'
```

- Expect HTTP 200 responses across all endpoints.
- `/system/status` should report `llm.available: true` and a non-zero `collection_count`.
- The sample query should return a natural-language answer plus at least one source file.

### Changing Upload Directory

To use a different directory for uploads, edit `app/main.py`:

```python
UPLOAD_DIR = Path("/app/data")  # Change this path
```

---

## Security Notes

✅ **What's Secure:**
- All data processing happens locally
- No external API calls to OpenAI, Anthropic, etc.
- Documents never leave your machine
- No telemetry or tracking (ChromaDB telemetry can be disabled)

⚠️ **Security Considerations:**
- Web interface has no authentication (suitable for local use only)
- **Do not expose port 8001 to the internet** without adding authentication
- Keep Docker Desktop updated
- Use trusted document sources only
- The system runs locally, but uploaded files are stored on disk

### Adding Authentication (Optional)

For production use, consider adding authentication:

```python
# Example: Basic Auth in FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(security)):
    # Add authentication logic
    pass
```

---

## Performance Tips

1. **First Query is Slow:** The first query loads the model into memory. Subsequent queries will be much faster.

2. **Batch Upload:** Upload multiple files at once instead of one at a time.

3. **Document Size:** Very large PDFs (100+ pages) may slow down processing. Consider splitting them.

4. **Model Selection:** Smaller models (7B parameters) are faster than larger ones (13B+).

5. **Resource Allocation:** Give Docker Desktop more RAM in Settings → Resources.

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check Docker logs:** `docker compose logs`
2. **Verify all services are running:** `docker compose ps`
3. **Ensure `.env` file is properly configured**
4. **Try restarting services:** `docker compose restart`
5. **Check browser console** (F12) for JavaScript errors
6. **Rebuild containers:** `docker compose up --build -d`

---

## Appendix: Keyboard Shortcuts

**In Chat Interface:**
- `Enter` - Send message
- `Ctrl/Cmd + K` - Focus on chat input (if implemented)

**In Browser:**
- `F12` - Open developer console
- `Ctrl/Cmd + R` - Refresh page
- `Ctrl/Cmd + Shift + R` - Hard refresh (clears cache)

---

**Version:** 2.5 (Enhanced Embedding Status Bar)  
**Last Updated:** November 2025

### What's New in Version 2.5 (Enhanced Embedding Status Bar)

- 📊 **Real System Metrics** - Live CPU and memory usage powered by `psutil` (no more simulated data)
- 📄 **Current File Display** - See exactly which file is being processed during embedding
- 🔢 **File Progress Counter** - Shows "File X of Y" so you know how many files remain
- 📈 **Progress Percentage** - Visible percentage (0-100%) directly inside the progress bar
- ⚡ **Processing Speed** - Displays real-time chunks/second during embedding
- ⏱️ **Estimated Time Remaining** - Smart ETA calculation (shows seconds, minutes, or hours)
- 🎨 **Animated Progress Bar** - Beautiful gradient animation (blue → purple → green) with pulsing effect
- 🎯 **Enhanced Visual Feedback** - File badge, processing stats section, and better spacing
- 🔌 **New API Endpoint** - `/system/resources` for real-time CPU/Memory monitoring

### What's New in Version 2.4 (Model Selection & Defaults)

- ⚡ **New Default Model: gemma2:2b** - Fast, efficient, privacy-focused (1.6 GB)
- 🔄 **Improved Model Selection** - "Change Model" button now works perfectly with instant switching
- 📋 **Current Model Display** - Shows which model is active in the LLM status card
- 🎯 **Pre-selected Model** - Modal automatically selects the current model
- ✨ **Seamless Switching** - Change models on-the-fly without restarting services
- 🚦 **Traffic Light Indicators** - Green (ready), Orange (loading), Red (error) for all system components
- 📚 **Better Source Citations** - Numbered sources with excerpts in chat responses
- 💾 **Database Status** - New dedicated database card with document count and traffic light

### What's New in Version 2.3 (10/10 UX Polish)

- ✨ **Toast Notifications** - Modern slide-in notifications for all user actions (upload, process, model switch)
- 🎯 **Empty State Improvements** - "Connecting..." and "Checking..." instead of "-" placeholders
- 🖱️ **Enhanced Micro-Interactions** - Hover effects on all cards and buttons with spring animations
- ♿ **Perfect Touch Targets** - All interactive elements are minimum 44x44px per Apple HIG
- 🔄 **Loading States** - Animated spinners and visual feedback during async operations
- 💍 **Focus States** - Clear blue outline with shadow for keyboard navigation
- 🎭 **Entrance Animations** - Smooth fadeInUp animations for metric cards and file cards
- 📱 **Responsive Verified** - Tested at 375px, 768px, 1024px, 1440px breakpoints
- 💡 **Helpful Tooltips** - Contextual help on hover for complex UI elements
- 🎨 **Cross-Browser Polish** - Firefox scrollbars, IE11 fallbacks, Safari optimizations

### What's New in Version 2.2

- 🤖 **LLM Model Management** - Select and switch between models dynamically without restarting
- ➕ **Add New Models** - Pull and download new Ollama models directly from the UI
- 📊 **Pulse Metrics Dashboard** - Live system status with real-time updates (API, LLM, Database, Alarms)
- 📁 **Enhanced File Display** - Beautiful file cards with icons, type badges, and smooth animations
- 📈 **File Types Grid** - Visual overview of file categories with counts
- 💬 **Dynamic Chat Window** - Message timestamps, expandable sources, improved spacing
- 📱 **Fully Responsive** - Adapts perfectly to all browser sizes (mobile, tablet, desktop)
- ⚡ **Real-Time Updates** - System status polls every 3 seconds automatically

### What's New in Version 2.1

- ✨ **Apple Liquid Glass Design** - Modern glassmorphism UI with translucent panels
- 🌙 **Automatic Dark Mode** - Adapts to your system preferences
- 🎨 **SF Symbols Icons** - Apple-style iconography throughout
- 📱 **Enhanced Animations** - Smooth spring physics for natural interactions
- 🎯 **Improved Accessibility** - ARIA labels and semantic HTML
- 💎 **Glass Effects** - Beautiful backdrop blur and transparency effects

