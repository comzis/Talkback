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

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings
)
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

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
# 1. Local LLM (Your preferred Granite model)
Settings.llm = Ollama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url="http://ollama:11434", # Use Docker service name
    request_timeout=120.0
)
# 2. Local Embedding Model
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

# --- FastAPI App ---
app = FastAPI(title="Secure Local RAG API")

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("/app/data")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Global state for ingestion progress
ingestion_status: Dict = {
    "status": "idle",  # idle, processing, completed, error
    "progress": 0,      # 0-100
    "current": 0,       # current document being processed
    "total": 0,         # total documents to process
    "message": "",      # status message
    "error": None       # error message if any
}

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    sources: list[dict]

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
    raise RuntimeError(f"Failed to connect to ChromaDB at {os.getenv('CHROMA_HOST')}:{os.getenv('CHROMA_PORT')}. "
                      f"Ensure ChromaDB service is running. Error: {e}")
    
# --- API Endpoints ---
def process_ingestion():
    """
    Background task to process document ingestion with progress tracking.
    """
    global ingestion_status
    
    try:
        # Update status to processing
        ingestion_status["status"] = "processing"
        ingestion_status["message"] = "Reading documents..."
        ingestion_status["progress"] = 10
        
        reader = SimpleDirectoryReader(input_dir="/app/data", recursive=True)
        documents = reader.load_data()
        
        if not documents:
            logger.warning("No documents found in /app/data. Skipping ingestion.")
            ingestion_status["status"] = "completed"
            ingestion_status["message"] = "No documents found to ingest."
            ingestion_status["progress"] = 100
            return
        
        ingestion_status["total"] = len(documents)
        ingestion_status["message"] = f"Processing {len(documents)} documents..."
        ingestion_status["progress"] = 20
        logger.info(f"Ingesting {len(documents)} documents...")
        
        # Process documents with progress updates
        ingestion_status["message"] = "Generating embeddings..."
        ingestion_status["progress"] = 40
        
        # This creates the index and stores embeddings in ChromaDB
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )
        
        # Update to completed
        ingestion_status["status"] = "completed"
        ingestion_status["message"] = f"Successfully ingested {len(documents)} documents."
        ingestion_status["progress"] = 100
        ingestion_status["current"] = len(documents)
        logger.info("Ingestion complete.")
        
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        ingestion_status["status"] = "error"
        ingestion_status["message"] = "Ingestion failed"
        ingestion_status["error"] = str(e)
        ingestion_status["progress"] = 0

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
    
    try:
        # 1. Load the index from the persistent ChromaDB store
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context
        )
        
        # 2. Fulfill "Citing sources" requirement
        # We will use a CitationQueryEngine
        
        # Custom prompt template to force the LLM to use citations
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
            # Get the file name (e.g., 'Pravilnik.pdf')
            file_name = node.metadata.get('file_name', 'Unknown Source')
            # Get the specific text chunk
            text_chunk = node.get_text()
            sources.append({"file": file_name, "text": text_chunk})

        return {
            "response": str(response),
            "sources": sources
        }
        
    except Exception as e:
        logger.error(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Simple health check to confirm the API is running."""
    return {"status": "ok"}

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
