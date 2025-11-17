# 🤖 Secure RAG Chatbot

A **100% local, privacy-focused** Retrieval-Augmented Generation (RAG) chatbot with a modern web interface. Chat with your documents using AI, with support for **30+ file formats** including PDFs, Word docs, Excel, PowerPoint, source code, and more.

## ✨ Features

- 🔒 **100% Local** - All data processing happens on your machine
- 💬 **Modern Web Interface** - Beautiful Apple Liquid Glass design with glassmorphism
- 🌙 **Automatic Dark Mode** - Adapts to your system preferences
- 📤 **Drag & Drop Upload** - Easy document management
- 📚 **30+ File Formats** - PDF, Word, Excel, PowerPoint, code files, JSON, XML, EPUB, and more
- 🎯 **Source Citations** - AI responses include document references
- 💾 **Persistent Storage** - ChromaDB vector database
- 🤖 **Flexible LLM** - Use any Ollama-compatible model
- 💻 **Code Analysis** - Upload and query source code
- 📊 **Data Processing** - Handle spreadsheets and data files
- 🎨 **SF Symbols Icons** - Apple-style iconography throughout
- ✨ **Smooth Animations** - Spring physics for natural interactions

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- 8GB+ RAM
- 5-10GB free disk space

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-private-repo-url>
cd secure-rag-project

# Create environment file
cat > .env << EOF
OLLAMA_MODEL=gemma2:2b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF
```

### 2. Start Services

```bash
# Build and start all services
docker compose up --build -d

# Download the default LLM model (fast and efficient - 1.6 GB)
docker exec ollama_service ollama pull gemma2:2b

# Check status
docker compose ps
```

### 3. Access the Chatbot

Open your browser and navigate to:

```
http://localhost:8001
```

### 4. Upload Documents and Chat!

1. Drag & drop files into the glass-style upload area (30+ formats supported)
2. Click "Upload Files" button
3. Click "Process Documents" button
4. Start asking questions in the beautiful chat interface!

## 📁 Supported File Formats

### Documents & Text
PDF, Word (DOCX/DOC), OpenDocument (ODT), Plain Text (TXT), Markdown (MD), reStructuredText (RST), Rich Text Format (RTF)

### Presentations & Data
PowerPoint (PPTX), Excel (XLSX), CSV

### Web & Configuration
JSON, XML, HTML

### Source Code
Python, JavaScript/TypeScript, Java, C/C++, Go, Rust, PHP, Ruby, Swift, Kotlin, and more

### eBooks
EPUB

## 📖 Documentation

For detailed setup instructions, API documentation, and troubleshooting:

👉 **[Read the Complete User Guide](USER_GUIDE.md)**

## 🏗️ Architecture

```
User Browser (Port 8001)
         ↓
    FastAPI + LlamaIndex
    ↙              ↘
ChromaDB          Ollama
(Vectors)         (LLM)
```

- **FastAPI**: Web framework and chatbot interface
- **LlamaIndex**: RAG orchestration with 30+ file readers
- **ChromaDB**: Vector database for embeddings
- **Ollama**: Local LLM inference (gemma2:2b default, llama2, llama3, mistral, etc.)
- **HuggingFace**: Embedding generation (BAAI/bge-small-en-v1.5)

## 💡 Use Cases

- **Documentation Hub**: Query across all your project docs
- **Code Review Assistant**: Upload source code and ask questions
- **Business Intelligence**: Analyze Excel reports and presentations
- **Research Assistant**: Process academic papers and research notes
- **Learning Tool**: Create a personal AI tutor with your study materials

## 🔧 Configuration

### Available LLM Models

- `gemma2:2b` - Gemma 2 2B ⚡ **Default & Recommended** (very fast, 1.6 GB, privacy-focused)
- `llama2` - Llama 2 7B (balanced performance, 3.8 GB)
- `llama3` - Llama 3 8B (newer, better quality, 4.7 GB)
- `mistral` - Mistral 7B (high quality, 4.1 GB)
- `phi3` - Phi-3 Mini (efficient, 2.3 GB)

### Change Model

```bash
# Option A: Switch via Web UI (instant, no restart)
# 1. Open http://localhost:8001
# 2. Click "Change Model" button
# 3. Select from dropdown

# Option B: Change default in .env
OLLAMA_MODEL=llama3

# Restart services
docker compose restart rag-api

# Download new model if needed
docker exec ollama_service ollama pull llama3
```

## 🛠️ Development

### Project Structure

```
secure-rag-project/
├── app/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile          # API container
│   └── static/             # Chatbot UI
│       ├── index.html
│       ├── style.css
│       └── script.js
├── data/                   # Your documents (gitignored)
├── chroma_data/           # Vector DB storage (gitignored)
├── docker-compose.yml     # Service orchestration
├── .env                   # Configuration (gitignored)
└── USER_GUIDE.md         # Complete documentation
```

### API Endpoints

- `GET /` - Chatbot interface
- `POST /upload` - Upload files
- `POST /ingest` - Process documents
- `GET /ingest/status` - Check processing status
- `POST /query` - Ask questions
- `GET /health` - Health check

## 🐛 Troubleshooting

### Common Issues

**Problem: Model not found error**
```bash
# Download the default model first
docker exec ollama_service ollama pull gemma2:2b
```

**Problem: Containers not starting**
```bash
# Check Docker is running
docker ps

# View logs
docker compose logs -f
```

**Problem: Upload fails**
```bash
# Ensure data directory exists
mkdir -p data

# Check file format is supported (see USER_GUIDE.md)
```

For more troubleshooting, see [USER_GUIDE.md](USER_GUIDE.md).

## 🔐 Privacy & Security

- **100% Local Processing**: No data leaves your machine
- **No Cloud Services**: All AI inference happens locally
- **Persistent Data**: Stored in local Docker volumes
- **Your Control**: You own all your data and models

## 📝 License

This project is for private use. All rights reserved.

## 🤝 Contributing

This is a private repository. For questions or issues, contact the repository owner.

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [LlamaIndex](https://www.llamaindex.ai/)
- [ChromaDB](https://www.trychroma.com/)
- [Ollama](https://ollama.ai/)
- [HuggingFace](https://huggingface.co/)

---

**Made with ❤️ for privacy-conscious AI enthusiasts**

