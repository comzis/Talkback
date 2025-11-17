# app/main.py
import os
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict
import asyncio
import mimetypes

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
)
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

from monitoring import LangChainMonitor

# --- Setup ---
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = {
    "OLLAMA_MODEL": "LLM model name for Ollama",
    "CHROMA_HOST": "ChromaDB host address",
    "CHROMA_PORT": "ChromaDB port number"
}

missing_vars = []
for var, description in required_env_vars.items():
    if not os.getenv(var):
        missing_vars.append(f"{var} ({description})")

if missing_vars:
    error_msg = f"Missing required environment variables:\n" + "\n".join(f"  - {var}" for var in missing_vars)
    logger.error(error_msg)
    raise ValueError(error_msg)

# --- Global Settings (LlamaIndex) ---
# Use local models for 100% data privacy
# 1. Local LLM (Default: gemma2:2b - fast, efficient, privacy-focused)
Settings.llm = Ollama(
    model=os.getenv("OLLAMA_MODEL", "gemma2:2b"),
    base_url="http://ollama:11434", # Use Docker service name
    request_timeout=120.0
)
# 2. Local Embedding Model
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

# --- FastAPI App ---
app = FastAPI(title="Secure Local RAG API")
monitor = LangChainMonitor()

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("/app/data")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Global state for ingestion progress and cached index
ingestion_status: Dict = {
    "status": "idle",  # idle, processing, completed, error
    "progress": 0,      # 0-100
    "current": 0,       # current document being processed
    "total": 0,         # total documents to process
    "message": "",      # status message
    "error": None       # error message if any
}

# Cached index built from the persistent Chroma vector store.
# This avoids recreating the index on every query and is refreshed after ingestion.
cached_index: VectorStoreIndex | None = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    sources: list[dict]

class LLMSelectRequest(BaseModel):
    model: str

class LLMPullRequest(BaseModel):
    model: str

class MonitoringConfigRequest(BaseModel):
    api_key: str = ""
    project: str = "Secure RAG Monitoring"
    enabled: bool = True

# --- ChromaDB Connection ---
try:
    # Connect to ChromaDB container
    db = chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST"), 
        port=os.getenv("CHROMA_PORT")
    )
    # Get or create the collection (like a table)
    chroma_collection = db.get_or_create_collection("rag_collection")
    
    # Create the LlamaIndex vector store
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    # Create the LlamaIndex storage context
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    logger.info("Successfully connected to ChromaDB")
    
except Exception as e:
    logger.error(f"Error connecting to ChromaDB: {e}")
    raise RuntimeError(
        f"Failed to connect to ChromaDB at {os.getenv('CHROMA_HOST')}:{os.getenv('CHROMA_PORT')}. "
        f"Ensure ChromaDB service is running. Error: {e}"
    )
    
# --- Helper functions ---

def get_or_create_cached_index() -> VectorStoreIndex:
    """
    Return the cached VectorStoreIndex if available, otherwise create it from the
    existing vector store and storage context, cache it, and return it.
    """
    global cached_index

    if cached_index is not None:
        return cached_index

    logger.info("Creating VectorStoreIndex from existing vector store for query")
    cached_index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    return cached_index
    
# --- API Endpoints ---
def process_ingestion():
    """
    Background task to process document ingestion with progress tracking.
    """
    global ingestion_status, cached_index

    ingest_run_id = monitor.start_run(
        name="document_ingestion",
        run_type="chain",
        inputs={"data_path": str(UPLOAD_DIR)},
        tags=["ingestion"],
    )
    
    try:
        # Update status to processing
        ingestion_status["status"] = "processing"
        ingestion_status["message"] = "Reading documents..."
        ingestion_status["progress"] = 10
        
        reader = SimpleDirectoryReader(input_dir="/app/data", recursive=True)
        documents = reader.load_data()
        
        doc_count = len(documents)
        if not documents:
            logger.warning("No documents found in /app/data. Skipping ingestion.")
            ingestion_status["status"] = "completed"
            ingestion_status["message"] = "No documents found to ingest."
            ingestion_status["progress"] = 100
            monitor.end_run(
                ingest_run_id,
                outputs={
                    "status": "no_documents",
                    "documents": 0,
                },
            )
            return
        
        ingestion_status["total"] = doc_count
        ingestion_status["message"] = f"Processing {doc_count} documents..."
        ingestion_status["progress"] = 20
        logger.info(f"Ingesting {doc_count} documents...")
        
        # Process documents with progress updates
        ingestion_status["message"] = "Generating embeddings..."
        ingestion_status["progress"] = 40
        
        # This creates the index and stores embeddings in ChromaDB
        new_index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )

        # Update cached index so subsequent queries can reuse it efficiently
        cached_index = new_index
        
        # Update to completed
        ingestion_status["status"] = "completed"
        ingestion_status["message"] = f"Successfully ingested {doc_count} documents."
        ingestion_status["progress"] = 100
        ingestion_status["current"] = doc_count
        logger.info("Ingestion complete.")
        monitor.end_run(
            ingest_run_id,
            outputs={
                "status": "completed",
                "documents": doc_count,
            },
        )
        
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        ingestion_status["status"] = "error"
        ingestion_status["message"] = "Ingestion failed"
        ingestion_status["error"] = str(e)
        ingestion_status["progress"] = 0
        monitor.end_run(
            ingest_run_id,
            error=str(e),
        )

@app.post("/ingest")
async def ingest_documents(background_tasks: BackgroundTasks):
    """
    Ingests all documents from the local '/app/data' directory.
    This directory is mapped from './data' on your host.
    Runs in background and updates progress status.
    """
    global ingestion_status
    
    # Check if already processing
    if ingestion_status["status"] == "processing":
        return {
            "message": "Ingestion already in progress",
            "status": ingestion_status["status"]
        }
    
    # Reset status
    ingestion_status = {
        "status": "processing",
        "progress": 0,
        "current": 0,
        "total": 0,
        "message": "Starting ingestion...",
        "error": None
    }
    
    # Start background task
    background_tasks.add_task(process_ingestion)
    
    return {
        "message": "Ingestion started",
        "status": "processing"
    }

@app.get("/ingest/status")
async def get_ingestion_status():
    """
    Get the current status of document ingestion.
    """
    return ingestion_status

@app.post("/query", response_model=QueryResponse)
async def query_index(request: QueryRequest):
    """
    Handles a user's query using the RAG logic and returns a
    response with source citations, as per your guideline.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    query_run_id = monitor.start_run(
        name="rag_query",
        run_type="chain",
        inputs={"query": request.query},
        tags=["query", "rag"],
    )
    
    try:
        # Check if we have any documents indexed
        collection_count = chroma_collection.count()
        if collection_count == 0:
            monitor.end_run(
                query_run_id,
                outputs={
                    "status": "no_documents",
                },
            )
            return {
                "response": "I don't have any documents indexed yet. Please upload files and click 'Process Documents' first.",
                "sources": []
            }
        
        # 1. Load or create the index from the persistent ChromaDB store,
        # using the in-memory cache for performance.
        index = get_or_create_cached_index()
        
        # 2. Fulfill "Citing sources" requirement
        # We will use a CitationQueryEngine
        
        # Custom prompt template to force the LLM to use citations
        qa_template = PromptTemplate(
            "You are Sentinel Spark ⚡, a friendly AI superhero guardian! You're helpful, entertaining, and love making references to superheroes and tech.\n\n"
            "Your personality:\n"
            "- Enthusiastic and encouraging (use phrases like 'Great question!', 'Awesome!', 'Let's dive in!')\n"
            "- Make occasional superhero references (Spider-Man, Iron Man, Avengers, etc.)\n"
            "- Add a touch of humor when appropriate\n"
            "- Be warm and supportive\n\n"
            "Answer the user's question based on the provided context.\n"
            "IMPORTANT: When you use information, you MUST cite the source using [source_number].\n"
            "Example: The sky is blue [1]. Python is awesome [2].\n\n"
            "If the context doesn't have the answer, be honest but stay in character!\n"
            "---------------------\n"
            "Context: {context_str}\n"
            "---------------------\n"
            "Question: {query_str}\n"
            "Answer (as Sentinel Spark): "
        )

        query_engine = CitationQueryEngine.from_args(
            index,
            similarity_top_k=3,
            # Fulfill RAG Logic: Retrieval -> Augmentation -> Generation
            citation_qa_template=qa_template,
        )

        # 3. Generate the response
        response = query_engine.query(request.query)
        
        # 4. Process sources for a clean API response
        sources = []
        for node in response.source_nodes:
            # Get the file name (e.g., 'Python Basics.pdf')
            file_name = node.metadata.get('file_name', 'Unknown Source')
            # Get the specific text chunk
            text_chunk = node.get_text()
            # Clean up the filename for better display
            display_name = file_name if file_name != 'Unknown Source' else 'Document'
            sources.append({
                "source": display_name,  # Changed from "file" to "source" for frontend consistency
                "text": text_chunk[:500]  # Limit text to 500 chars for cleaner display
            })

        monitor.end_run(
            query_run_id,
            outputs={
                "status": "completed",
                "sources": [src["source"] for src in sources],
            },
        )

        return {
            "response": str(response),
            "sources": sources
        }
        
    except Exception as e:
        logger.error(f"Error during query: {e}")
        monitor.end_run(query_run_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Simple health check to confirm the API is running."""
    return {"status": "ok"}

@app.get("/system/status")
async def get_system_status():
    """
    Comprehensive system status including API, LLM, Database, and alarms.
    """
    import time
    import httpx
    
    status = {
        "timestamp": time.time(),
        "api": {
            "status": "online",
            "uptime": "running"
        },
        "llm": {
            "status": "unknown",
            "available": False,
            "model_configured": None,
            "response_time_ms": None,
            "error": None
        },
        "database": {
            "status": "unknown",
            "connected": False,
            "collection_count": 0,
            "error": None
        },
        "alarms": []
    }
    
    # Check LLM status
    try:
        llm_status = await get_llm_status()
        status["llm"] = llm_status
        if not llm_status.get("available", False):
            status["alarms"].append({
                "type": "warning",
                "component": "llm",
                "message": f"LLM is {llm_status.get('status', 'unknown')}: {llm_status.get('error', 'Unknown error')}"
            })
    except Exception as e:
        status["llm"]["status"] = "error"
        status["llm"]["error"] = str(e)
        status["alarms"].append({
            "type": "error",
            "component": "llm",
            "message": f"Failed to check LLM status: {str(e)}"
        })
    
    # Check Database status
    try:
        collection_count = chroma_collection.count()
        status["database"]["status"] = "online"
        status["database"]["connected"] = True
        status["database"]["collection_count"] = collection_count
    except Exception as e:
        status["database"]["status"] = "offline"
        status["database"]["connected"] = False
        status["database"]["error"] = str(e)
        status["alarms"].append({
            "type": "error",
            "component": "database",
            "message": f"Database connection error: {str(e)}"
        })
    
    # Check ingestion status for warnings
    if ingestion_status.get("status") == "error":
        status["alarms"].append({
            "type": "warning",
            "component": "ingestion",
            "message": f"Ingestion error: {ingestion_status.get('error', 'Unknown error')}"
        })
    
    # Add monitoring status
    status["monitoring"] = {
        "enabled": monitor.enabled,
        "project": monitor.project_name if monitor.enabled else None,
        "docs_url": "https://docs.smith.langchain.com/overview",
        "dashboard_url": "https://smith.langchain.com/"
    }
    
    return status

@app.post("/monitoring/configure")
async def configure_monitoring(request: MonitoringConfigRequest):
    """
    Enable or disable LangChain monitoring with API key configuration.
    """
    try:
        global monitor
        
        if request.enabled:
            # Enable monitoring
            if not request.api_key:
                raise HTTPException(status_code=400, detail="API key is required to enable monitoring")
            
            # Set environment variables
            os.environ["LANGCHAIN_MONITORING"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = request.project
            os.environ["LANGSMITH_API_KEY"] = request.api_key
            os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
            
            # Reinitialize monitor
            monitor = LangChainMonitor()
            
            if not monitor.enabled:
                raise HTTPException(status_code=500, detail="Failed to initialize monitoring. Check your API key.")
            
            logger.info(f"LangChain monitoring enabled for project: {request.project}")
            
            return {
                "message": "Monitoring enabled successfully",
                "enabled": True,
                "project": request.project
            }
        else:
            # Disable monitoring
            os.environ["LANGCHAIN_MONITORING"] = "false"
            monitor = LangChainMonitor()
            
            logger.info("LangChain monitoring disabled")
            
            return {
                "message": "Monitoring disabled",
                "enabled": False
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/types")
async def get_file_types():
    """
    Get file type statistics grouped by category.
    """
    try:
        files_data = await list_uploaded_files()
        files = files_data.get("files", [])
        by_type = files_data.get("by_type", {})
        
        # Get detailed breakdown
        type_details = {}
        for file_type in ['document', 'code', 'data', 'image', 'other']:
            type_files = [f for f in files if f["type"] == file_type]
            total_size = sum(f["size"] for f in type_files)
            
            type_details[file_type] = {
                "count": by_type.get(file_type, 0),
                "total_size": total_size,
                "files": [
                    {
                        "name": f["filename"],
                        "size": f["size"],
                        "extension": f["extension"]
                    }
                    for f in type_files[:10]  # Limit to first 10 for performance
                ]
            }
        
        return {
            "by_type": type_details,
            "total_files": len(files),
            "total_size": sum(f["size"] for f in files)
        }
    except Exception as e:
        logger.error(f"Error getting file types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chatbot interface."""
    try:
        with open("/app/static/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Chatbot interface not found</h1>", status_code=404)

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload one or more files to the data directory for ingestion.
    """
    try:
        uploaded_files = []
        
        for file in files:
            # Save file to the data directory
            file_path = UPLOAD_DIR / file.filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded_files.append(file.filename)
            logger.info(f"Uploaded file: {file.filename}")
        
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} file(s).",
            "files": uploaded_files
        }
        
    except Exception as e:
        logger.error(f"Error during file upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_file_type(filename: str) -> str:
    """
    Determine file type category from extension.
    Returns: 'document', 'code', 'data', 'image', 'other'
    """
    ext = Path(filename).suffix.lower()
    
    # Documents
    doc_exts = {'.pdf', '.doc', '.docx', '.odt', '.txt', '.md', '.rst', '.rtf', '.epub'}
    # Code files
    code_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.sh', '.bash', '.zsh', '.yaml', '.yml', '.json', '.xml', '.html', '.css', '.scss', '.less'}
    # Data/Spreadsheet
    data_exts = {'.xlsx', '.xls', '.csv', '.json', '.xml'}
    # Images
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}
    # Presentations
    pres_exts = {'.pptx', '.ppt', '.odp'}
    
    if ext in doc_exts or ext in pres_exts:
        return 'document'
    elif ext in code_exts:
        return 'code'
    elif ext in data_exts:
        return 'data'
    elif ext in image_exts:
        return 'image'
    else:
        return 'other'

@app.get("/files")
async def list_uploaded_files():
    """
    List all files currently in the data directory, sorted by file type.
    """
    try:
        files = []
        if UPLOAD_DIR.exists():
            for file_path in UPLOAD_DIR.rglob("*"):
                if file_path.is_file():
                    # Get relative path from UPLOAD_DIR for cleaner display
                    rel_path = file_path.relative_to(UPLOAD_DIR)
                    filename = rel_path.name
                    file_type = get_file_type(filename)
                    
                    files.append({
                        "name": str(rel_path),
                        "filename": filename,
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                        "type": file_type,
                        "extension": Path(filename).suffix.lower()
                    })
        
        # Sort by type first, then by name within each type
        type_order = {'document': 0, 'code': 1, 'data': 2, 'image': 3, 'other': 4}
        files_sorted = sorted(files, key=lambda x: (type_order.get(x["type"], 99), x["name"].lower()))
        
        return {
            "files": files_sorted,
            "count": len(files),
            "by_type": {
                file_type: len([f for f in files if f["type"] == file_type])
                for file_type in ['document', 'code', 'data', 'image', 'other']
            }
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/llm/models")
async def list_llm_models():
    """
    List all available Ollama models and return the currently configured model.
    """
    try:
        import httpx
        ollama_url = "http://ollama:11434/api/tags"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                models = []
                for model in models_data:
                    models.append({
                        "name": model.get("name", ""),
                        "size": model.get("size", 0),
                        "modified": model.get("modified_at", "")
                    })
                
                # Get the current model from environment
                current_model = os.getenv("OLLAMA_MODEL", "gemma2:2b")
                
                return {
                    "models": models,
                    "count": len(models),
                    "current_model": current_model
                }
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch models from Ollama")
    except Exception as e:
        logger.error(f"Error listing LLM models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/llm/select")
async def select_llm_model(request: LLMSelectRequest):
    """
    Switch to a different LLM model.
    """
    try:
        import httpx
        # First verify the model exists
        ollama_url = "http://ollama:11434/api/tags"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                # Check if model exists (exact match or starts with)
                model_found = any(m.startswith(request.model) or request.model == m for m in model_names)
                
                if not model_found:
                    raise HTTPException(status_code=404, detail=f"Model '{request.model}' not found. Available models: {model_names}")
                
                # Update the global LLM settings
                global Settings
                Settings.llm = Ollama(
                    model=request.model,
                    base_url="http://ollama:11434",
                    request_timeout=120.0
                )
                
                # Update environment variable (in-memory, won't persist to .env file)
                os.environ["OLLAMA_MODEL"] = request.model
                
                # Clear cached index to force reload with new model
                global cached_index
                cached_index = None
                
                logger.info(f"Switched LLM model to: {request.model}")
                
                return {
                    "message": f"Successfully switched to model: {request.model}",
                    "model": request.model
                }
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to connect to Ollama")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting LLM model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/llm/pull")
async def pull_llm_model(request: LLMPullRequest, background_tasks: BackgroundTasks):
    """
    Pull/download a new model from Ollama.
    """
    try:
        import httpx
        ollama_url = f"http://ollama:11434/api/pull"
        
        # Start the pull in background
        async def pull_model():
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", ollama_url, json={"name": request.model}) as response:
                        if response.status_code != 200:
                            logger.error(f"Failed to pull model: {response.status_code}")
                            return
                        # Stream the response to show progress
                        async for line in response.aiter_lines():
                            if line:
                                logger.info(f"Ollama pull: {line}")
            except Exception as e:
                logger.error(f"Error pulling model: {e}")
        
        background_tasks.add_task(pull_model)
        
        return {
            "message": f"Started pulling model: {request.model}",
            "model": request.model,
            "status": "pulling"
        }
    except Exception as e:
        logger.error(f"Error initiating model pull: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/llm/status")
async def get_llm_status():
    """
    Check if the LLM (Ollama) is running and responding.
    Enhanced with response time metrics.
    """
    try:
        import httpx
        import time
        ollama_url = f"http://ollama:11434/api/tags"
        
        start_time = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_name = os.getenv("OLLAMA_MODEL", "gemma2:2b")
                model_available = any(m.get("name", "").startswith(model_name) for m in models)
                
                return {
                    "status": "online",
                    "available": True,
                    "model_configured": model_name,
                    "model_available": model_available,
                    "models_installed": [m.get("name", "") for m in models],
                    "response_time_ms": round(response_time, 2)
                }
            else:
                return {
                    "status": "error",
                    "available": False,
                    "error": f"Ollama returned status {response.status_code}",
                    "response_time_ms": round(response_time, 2)
                }
    except Exception as e:
        logger.error(f"Error checking LLM status: {e}")
        return {
            "status": "offline",
            "available": False,
            "error": str(e),
            "response_time_ms": None
        }
