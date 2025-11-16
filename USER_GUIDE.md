# Secure RAG Chatbot - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Supported File Formats (30+)](#-supported-file-formats-30)
5. [Using the Chatbot Interface](#using-the-chatbot-interface)
6. [API Endpoints (Advanced)](#api-endpoints-advanced)
7. [Example Workflows](#example-workflows)
8. [Troubleshooting](#troubleshooting)
9. [System Architecture](#system-architecture)
10. [Advanced Configuration](#advanced-configuration)

---

## Overview

The Secure RAG (Retrieval-Augmented Generation) Chatbot is a privacy-focused system that allows you to:
- Chat with your documents using a beautiful web interface
- Upload files directly through your browser
- Get AI-generated responses with source citations
- Keep all data 100% local (no cloud services)

**Key Features:**
- 🔒 **100% Local Processing** - All data stays on your machine
- 💬 **Interactive Chatbot** - Modern web interface with Apple Liquid Glass design
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
OLLAMA_MODEL=llama2
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

**Important:** 
- `OLLAMA_MODEL` - Specify your preferred Ollama model (e.g., `llama2`, `mistral`, `llama3`, `gemma2:2b`)
- `CHROMA_HOST` - Use `chromadb` for Docker networking
- `CHROMA_PORT` - Default ChromaDB port is `8000`

**Available Models:**
- `llama2` - Llama 2 7B (good balance, recommended for most users)
- `llama3` - Llama 3 8B (newer, better quality)
- `mistral` - Mistral 7B (high quality responses)
- `gemma2:2b` - Gemma 2 2B (very fast, lower resource usage)
- `phi3` - Phi-3 Mini (efficient, good for limited resources)

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
# Download your chosen model (this may take several minutes)
docker exec ollama_service ollama pull llama2

# Or use another model like:
# docker exec ollama_service ollama pull llama3
# docker exec ollama_service ollama pull mistral
# docker exec ollama_service ollama pull gemma2:2b
```

**Model Size & Performance Guide:**
- **llama2** (3.8 GB) - Balanced performance, good for most uses ✅ Recommended
- **llama3** (4.7 GB) - Better quality, slightly larger
- **mistral** (4.1 GB) - High quality responses
- **gemma2:2b** (1.6 GB) - Fast, great for lower-end systems
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

The interface consists of two main panels:

1. **Left Panel: Document Management**
   - Glass-style file upload area (drag & drop or click)
   - List of uploaded files with file type badges
   - Process documents button with lightning icon
   - Status messages with glass effects
   - Real-time status indicators (API Server, LLM)

2. **Right Panel: Chat Interface**
   - Glass-style chat history display
   - Message bubbles with glass effects
   - Message input box with rounded design
   - Send button with smooth animations

### Step-by-Step Guide

#### 1. Upload Documents

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

#### 2. Upload Files to Server

After selecting files:
1. Click the **"Upload Files"** button (with upload icon)
2. Wait for the upload to complete
3. You'll see a success message with glass-style notification: "Successfully uploaded X file(s)"
4. Uploaded files will appear in the file list with type badges and file size

#### 3. Process Documents

Once files are uploaded:
1. Click the **"Process Documents"** button (with lightning icon)
2. Watch the progress bar with glass-style design:
   - Progress percentage updates in real-time
   - Status messages show current processing stage
   - Smooth animations indicate activity
3. Wait while the system:
   - Reads all documents from the data folder
   - Generates embeddings using AI
   - Stores them in ChromaDB
4. You'll see: "Successfully ingested X documents" with success notification
5. The chat input will become active and ready for questions

**Note:** Processing time depends on:
- Number of documents
- Size of documents
- Your computer's processing power

#### 4. Ask Questions

Now you can chat with your documents:
1. Type your question in the rounded input box (glass-style design)
2. Press **Enter** or click the **Send button** (with send icon)
3. Watch smooth animations:
   - Your message slides in with spring physics
   - Loading dots appear while processing
   - Bot response animates in naturally
4. View the response with source citations:
   - Glass-style message bubbles
   - Source documents listed with file icons
   - Smooth scrolling to new messages

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
OLLAMA_MODEL=llama2
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# 4. Start services
docker compose up -d

# 5. Download the model
docker exec ollama_service ollama pull llama2

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

```bash
# 1. Update .env file with new model name
echo "OLLAMA_MODEL=llama2" > .env

# 2. Restart services
docker compose down
docker compose up -d

# 3. Download the new model
docker exec ollama_service ollama pull llama2

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
# Fast and recommended (3.8 GB)
docker exec ollama_service ollama pull llama2

# Better quality (4.7 GB)
docker exec ollama_service ollama pull llama3

# High quality (4.1 GB)
docker exec ollama_service ollama pull mistral

# Very fast, small size (1.6 GB)
docker exec ollama_service ollama pull gemma2:2b
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
   docker exec ollama_service ollama pull granite-3.1-8b-instruct
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

**Version:** 2.1 (Apple Liquid Glass Design)  
**Last Updated:** November 2025

### What's New in Version 2.1

- ✨ **Apple Liquid Glass Design** - Modern glassmorphism UI with translucent panels
- 🌙 **Automatic Dark Mode** - Adapts to your system preferences
- 🎨 **SF Symbols Icons** - Apple-style iconography throughout
- 📱 **Enhanced Animations** - Smooth spring physics for natural interactions
- 🎯 **Improved Accessibility** - ARIA labels and semantic HTML
- 💎 **Glass Effects** - Beautiful backdrop blur and transparency effects
