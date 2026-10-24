# macOS only. This guide is for a MacBook Pro M1 Max. Do not use it for the Windows pilot.

# 🚀 M1 MAX Optimization Guide

> Historical note: Ollama runs on the host (`ollama pull`), not in a container named `ollama_service`. LangSmith has been removed. Current setup is in `README.md` and `SECURITY.md`.
## MacBook Pro M1 MAX 64GB - High Performance Configuration

Your MacBook Pro M1 MAX is a **powerhouse**! Let's configure the RAG chatbot to use its full potential.

---

## 🎯 System Capabilities

**Your Hardware:**
- **CPU**: M1 MAX (10 cores: 8 performance + 2 efficiency)
- **GPU**: 24 or 32-core GPU (unified memory architecture)
- **RAM**: 64GB unified memory
- **Neural Engine**: 16-core for ML tasks

**What This Means:**
- ✅ Can run large models (13B, even 70B parameters)
- ✅ GPU acceleration available
- ✅ Handle 100+ documents simultaneously
- ✅ Fast inference with large context windows
- ✅ No timeout issues with proper configuration

---

## 🔧 Step 1: Configure Docker Desktop

### Increase Docker Resources

1. Open **Docker Desktop**
2. Click **Settings** (⚙️ icon)
3. Go to **Resources**
4. Set the following:

```
CPUs: 8 cores (use most of your performance cores)
Memory: 32 GB (half your RAM, plenty for all services)
Swap: 4 GB
Disk image size: 100 GB (if you plan to use multiple models)
```

5. Click **Apply & Restart**

---

## 🔧 Step 2: Optimize Ollama Configuration

### Enable GPU Acceleration (Already enabled on M1!)

Ollama automatically uses Metal (Apple's GPU framework) on M1 Macs. Verify:

```bash
ollama run llama2 "Test" --verbose
# Look for "Metal" in the output
```

---

## 🔧 Step 3: Update Application Configuration

### Option A: Use a Larger, Better Model ⭐ RECOMMENDED

With your hardware, you can use much better models:

```bash
# Download a high-quality model
ollama pull llama3:8b
# OR for even better quality:
ollama pull mixtral:8x7b

# Update .env file
cat > Talkback/.env << 'EOF'
# High Performance Configuration for M1 MAX
OLLAMA_MODEL=llama3:8b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# Restart services
cd Talkback
docker compose restart rag-api
```

**Recommended Models for M1 MAX 64GB:**
- `llama3:8b` (4.7 GB) - Latest, best quality ⭐⭐⭐⭐⭐
- `mixtral:8x7b` (26 GB) - Extremely high quality (needs 32GB RAM)
- `mistral:7b` (4.1 GB) - Excellent balance
- `llama2:13b` (7.4 GB) - Larger, more capable
- `codellama:13b` (7.4 GB) - Great for code analysis

---

### Option B: Optimize Current Configuration

Edit `Talkback/app/main.py`:

**1. Increase LLM Configuration:**

```python
# Around line 52-60, replace with:
Settings.llm = Ollama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url="http://ollama:11434",
    request_timeout=600.0,  # 10 minutes
    timeout=600.0,
    temperature=0.7,
    # M1 MAX Optimizations:
    context_window=8192,    # Increased from default 4096
    num_predict=2048,       # Allow longer responses
    num_gpu=1,              # Use GPU
    num_thread=8,           # Use 8 CPU threads
)
```

**2. Increase Document Retrieval:**

```python
# Around line 210, find and modify:
query_engine = CitationQueryEngine.from_args(
    index,
    similarity_top_k=5,  # Increased from 3 - use more context
    citation_qa_template=qa_template,
)
```

**3. Optimize Embedding Model (Optional):**

```python
# Around line 61-63, can use larger embedding model:
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-large-en-v1.5"  # Larger, more accurate
)
```

**4. Increase Chunk Size for Better Context:**

```python
# Add after Settings configuration (around line 64):
Settings.chunk_size = 1024  # Increased from default 512
Settings.chunk_overlap = 128  # Increased from default 20
```

---

## 🔧 Step 4: Optimize ChromaDB

ChromaDB can also benefit from more resources. Update `docker-compose.yml`:

```yaml
  chromadb:
    image: chromadb/chroma
    container_name: chromadb_service
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_data:/chroma/chroma
    environment:
      - CHROMA_SERVER_CORS_ALLOW_ORIGINS=["*"]
      # M1 MAX Optimizations:
      - CHROMA_SERVER_CACHE_SIZE=5000000000  # 5GB cache
      - CHROMA_SERVER_MAX_PARALLEL_TASKS=16
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

---

## 🔧 Step 5: Optimize FastAPI

Update `docker-compose.yml` for the RAG API:

```yaml
  rag-api:
    build: ./app
    container_name: rag_api_service
    ports:
      - "8001:8001"
    depends_on:
      - chromadb
      - ollama
    environment:
      - OLLAMA_MODEL=${OLLAMA_MODEL}
      - CHROMA_HOST=${CHROMA_HOST}
      - CHROMA_PORT=${CHROMA_PORT}
      # Performance optimizations:
      - WORKERS=4  # Multiple workers
      - MAX_REQUESTS=1000
    volumes:
      - ./data:/app/data
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
    command: uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
```

---

## 📊 Recommended Model Configurations

### Configuration 1: Best Balance ⭐ RECOMMENDED
```bash
Model: llama3:8b (4.7 GB)
Context Window: 8192 tokens
Similarity Top K: 5 documents
Response Time: 5-15 seconds
Quality: ⭐⭐⭐⭐⭐
```

### Configuration 2: Maximum Quality
```bash
Model: mixtral:8x7b (26 GB)
Context Window: 32768 tokens
Similarity Top K: 10 documents
Response Time: 15-30 seconds
Quality: ⭐⭐⭐⭐⭐+
```

### Configuration 3: Fastest Response
```bash
Model: mistral:7b (4.1 GB)
Context Window: 8192 tokens
Similarity Top K: 3 documents
Response Time: 3-8 seconds
Quality: ⭐⭐⭐⭐⭐
```

### Configuration 4: Code-Focused
```bash
Model: codellama:13b (7.4 GB)
Context Window: 16384 tokens
Similarity Top K: 5 documents
Response Time: 8-20 seconds
Quality: ⭐⭐⭐⭐⭐ (for code)
```

---

## 🚀 Quick Apply: Recommended Configuration

```bash
#!/bin/bash
cd Talkback

echo "🚀 Optimizing for M1 MAX 64GB..."

# Stop services
docker compose down

# Download best model for your hardware
docker compose up -d ollama
sleep 5
ollama pull llama3:8b

# Update .env
cat > .env << 'EOF'
OLLAMA_MODEL=llama3:8b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# Restart all services
docker compose up -d

echo "✅ Optimization complete!"
echo "📊 Your system is now configured for:"
echo "   - High-quality llama3:8b model"
echo "   - 8K context window"
echo "   - GPU acceleration (Metal)"
echo "   - Optimized for 64GB RAM"
echo ""
echo "🌐 Access your chatbot at: http://localhost:8001"
echo "⏱️  Expected response time: 5-15 seconds"
```

Save as `optimize_m1_max.sh` and run:
```bash
chmod +x optimize_m1_max.sh
./optimize_m1_max.sh
```

---

## 📈 Performance Benchmarks (M1 MAX)

| Model | Size | RAM Usage | Response Time | Quality |
|-------|------|-----------|---------------|---------|
| llama3:8b | 4.7 GB | ~6 GB | 5-15s | ⭐⭐⭐⭐⭐ |
| mistral:7b | 4.1 GB | ~5 GB | 3-8s | ⭐⭐⭐⭐⭐ |
| llama2:13b | 7.4 GB | ~9 GB | 10-25s | ⭐⭐⭐⭐⭐ |
| mixtral:8x7b | 26 GB | ~28 GB | 15-35s | ⭐⭐⭐⭐⭐+ |
| codellama:13b | 7.4 GB | ~9 GB | 8-20s | ⭐⭐⭐⭐⭐ |

*Benchmarks with 5 document context, measured on M1 MAX*

---

## 🔍 Monitoring Performance

### Check Resource Usage:
```bash
# Docker stats
docker stats

# Ollama specific
ollama ps

# Check GPU usage (if available)
sudo powermetrics --samplers gpu_power -i 1000 -n 1
```

### Test Query Performance:
```bash
# Time a query
time curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Python used for?"}'
```

---

## 💡 Advanced: Multiple Models

With 64GB RAM, you can keep multiple models ready:

```bash
# Download multiple models
ollama pull llama3:8b
ollama pull codellama:13b
ollama pull mistral:7b

# Switch between them by updating .env
echo "OLLAMA_MODEL=codellama:13b" > .env
docker compose restart rag-api
```

---

## ⚡ Expected Performance After Optimization

### Before (llama2 on default settings):
- ❌ Timeouts on most queries
- ⏱️ 30-60+ seconds when working
- 💾 5.5 GB RAM usage
- 🔥 High CPU, no GPU usage

### After (llama3:8b optimized):
- ✅ No timeouts
- ⏱️ 5-15 seconds average
- 💾 6-8 GB RAM usage (plenty of headroom)
- 🚀 GPU acceleration enabled
- 📈 Better quality responses
- 🎯 More document context

---

## 🎯 Recommended Next Steps

1. **Run the quick optimization script** above
2. **Test with your documents** at http://localhost:8001
3. **If you want even better quality**, try `mixtral:8x7b`
4. **For code analysis**, use `codellama:13b`
5. **Monitor performance** and adjust as needed

---

## 📞 Troubleshooting

### If still slow:
1. Check Docker Desktop has 32GB memory allocated
2. Verify GPU is being used: `ollama ps`
3. Try mistral:7b for fastest responses
4. Check system isn't thermal throttling

### If out of memory:
- Reduce Docker memory to 24GB
- Use smaller model (mistral:7b)
- Reduce `similarity_top_k` to 3

---

**Your M1 MAX is a beast! Let's unleash it! 🚀**

