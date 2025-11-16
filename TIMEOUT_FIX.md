# 🔧 Timeout Error - Root Cause & Solutions

## 🚨 Problem Identified

**Ollama is timing out on RAG queries** even though the model (llama2) is loaded.

### Root Cause:
- **Hardware Constraints**: Running on system with limited resources (7.7 GB RAM, CPU-only)
- **Model Loading**: llama2 (3.8 GB) is using 5.5GB RAM + high CPU
- **Endpoint Issue**: Ollama `/api/chat` endpoint times out after 2 minutes
- **Direct `/api/generate` works** but takes 17+ seconds for simple queries
- **RAG queries with 943 document chunks** exceed the timeout threshold

### Evidence from Logs:
```
# Direct test - SUCCESS (17 seconds)
[GIN] 2025/11/16 - 12:16:15 | 200 | 17.177949508s | POST "/api/generate"

# RAG API calls - TIMEOUT (2 minutes)
[GIN] 2025/11/16 - 12:18:25 | 500 | 2m0s | POST "/api/chat"
[GIN] 2025/11/16 - 12:24:13 | 500 | 2m0s | POST "/api/chat"
```

---

## ✅ Solutions (Choose One)

### **Solution 1: Use a Smaller, Faster Model** ⭐ RECOMMENDED

Switch to a lighter model that runs faster on your hardware:

```bash
# Stop services
docker compose down

# Download a faster model
docker compose up -d ollama
docker exec ollama_service ollama pull gemma2:2b

# Update .env file
cat > .env << 'EOF'
OLLAMA_MODEL=gemma2:2b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# Restart all services
docker compose up -d
```

**Gemma 2:2b Benefits:**
- ✅ Only 1.6 GB (vs llama2's 3.8 GB)
- ✅ 3-5x faster inference
- ✅ Lower RAM usage
- ✅ Still produces quality responses

**Alternative Fast Models:**
- `phi3` (2.3 GB) - Microsoft's efficient model
- `tinyllama` (637 MB) - Extremely fast for testing
- `qwen2:1.5b` (934 MB) - Good balance

---

### **Solution 2: Reduce Document Context**

Limit the number of documents sent to the LLM:

**Edit `app/main.py`:**

```python
# Around line 210 - find this section:
query_engine = CitationQueryEngine.from_args(
    index,
    similarity_top_k=3,  # CHANGE THIS: Reduce from 3 to 2 or 1
    citation_qa_template=qa_template,
)
```

Change `similarity_top_k=3` to `similarity_top_k=1` to send fewer documents.

Then restart:
```bash
docker compose restart rag-api
```

---

### **Solution 3: Use Streaming Responses** (Advanced)

Modify the code to use streaming, which is more reliable:

**Edit `app/main.py`:**

```python
# Add after imports
from llama_index.llms.ollama import Ollama

# Modify LLM initialization (around line 55):
Settings.llm = Ollama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url="http://ollama:11434",
    request_timeout=600.0,  # 10 minutes
    timeout=600.0,
    temperature=0.7,
    context_window=4096,  # Limit context
    num_predict=512,      # Limit response length
)
```

Then restart:
```bash
docker compose restart rag-api
```

---

### **Solution 4: Increase System Resources**

If using Docker Desktop:

1. Open **Docker Desktop → Settings → Resources**
2. Increase:
   - **CPUs**: 4+ cores
   - **Memory**: 12+ GB
   - **Swap**: 4+ GB
3. Click **Apply & Restart**
4. Restart services:
   ```bash
   docker compose down
   docker compose up -d
   ```

---

## 🎯 Recommended Action Plan

**For Best Results:**

1. **Switch to gemma2:2b** (fastest fix):
   ```bash
   docker compose down
   docker compose up -d ollama
   docker exec ollama_service ollama pull gemma2:2b
   echo "OLLAMA_MODEL=gemma2:2b" > .env
   echo "CHROMA_HOST=chromadb" >> .env
   echo "CHROMA_PORT=8000" >> .env
   docker compose up -d
   ```

2. **Test immediately**:
   ```bash
   # Wait 20 seconds for startup
   sleep 20
   
   # Test query
   curl -X POST http://localhost:8001/query \
     -H "Content-Type: application/json" \
     -d '{"query": "What is Python?"}' | python3 -m json.tool
   ```

3. **If still timing out**, also reduce `similarity_top_k=1` in code

---

## 📊 Model Comparison

| Model | Size | Speed | RAM | Quality | Best For |
|-------|------|-------|-----|---------|----------|
| **gemma2:2b** | 1.6 GB | ⚡⚡⚡⚡⚡ | 2-3 GB | ⭐⭐⭐⭐ | **Your system** ✅ |
| **phi3** | 2.3 GB | ⚡⚡⚡⚡ | 3-4 GB | ⭐⭐⭐⭐ | Good alternative |
| llama2 | 3.8 GB | ⚡⚡ | 5-6 GB | ⭐⭐⭐⭐⭐ | Needs more resources |
| mistral | 4.1 GB | ⚡⚡ | 5-6 GB | ⭐⭐⭐⭐⭐ | Needs more resources |
| llama3 | 4.7 GB | ⚡⚡ | 6-7 GB | ⭐⭐⭐⭐⭐ | High-end systems |

---

## 🔍 Testing

After applying fixes, test with:

```bash
# Simple query test
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hi"}' | python3 -m json.tool

# Full RAG test
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What topics are covered in the Python documents?"}' | python3 -m json.tool
```

**Expected response time:**
- gemma2:2b: 5-15 seconds
- phi3: 10-20 seconds  
- llama2: 30-60 seconds (if it works)

---

## 🆘 If Nothing Works

Your system may not have enough resources for local LLM inference. Consider:

1. **Reduce document count** - Process fewer documents at a time
2. **Use external API** - OpenAI, Anthropic, etc. (loses privacy)
3. **Upgrade hardware** - More RAM/CPU
4. **Use cloud deployment** - AWS, GCP with better specs

---

**Quick Fix Command (Copy & Paste):**

```bash
cd /Users/comzis/Projects/secure-rag-project && \
docker compose down && \
docker compose up -d ollama && \
sleep 5 && \
docker exec ollama_service ollama pull gemma2:2b && \
cat > .env << 'EOF'
OLLAMA_MODEL=gemma2:2b
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF
docker compose up -d && \
echo "✅ Switching to faster model. Wait 30 seconds then test at http://localhost:8001"
```

---

**Need Help?** Check the logs:
```bash
docker compose logs ollama --tail 20
docker compose logs rag-api --tail 20
```

