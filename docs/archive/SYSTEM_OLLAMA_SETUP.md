# Using System Ollama Instead of Docker Container

> Historical note: Ollama runs on the host (`ollama pull`), not in a container named `ollama_service`. LangSmith has been removed. Current setup is in `README.md` and `SECURITY.md`.

This guide explains how to use your system's Ollama installation instead of running it in a Docker container. This provides better performance by utilizing your system's resources directly.

## ✅ What Was Changed

### 1. **docker-compose.yml**
- Removed the `ollama` service
- Removed `ollama_data` volume
- Added `extra_hosts` to `rag-api` service to enable host network access
- Updated `depends_on` to only depend on `chromadb`

### 2. **app/main.py**
- Updated all Ollama URL references from `http://ollama:11434` to `http://host.docker.internal:11434`
- Made the base URL configurable via `OLLAMA_BASE_URL` environment variable
- Updated 5 locations:
  - LLM initialization
  - `/llm/models` endpoint
  - `/llm/select` endpoint
  - `/llm/pull` endpoint
  - `/llm/status` endpoint

## 📋 Prerequisites

### 1. Install Ollama on Your System

**macOS:**
```bash
brew install ollama
```

Or download from: https://ollama.ai/download

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from: https://ollama.ai/download

### 2. Start Ollama Service

**macOS/Linux:**
```bash
ollama serve
```

This will start Ollama on `http://localhost:11434`

**Verify it's running:**
```bash
curl http://localhost:11434/api/tags
```

### 3. Download Your Preferred Model

```bash
# Default model (recommended)
ollama pull gemma2:2b

# Or other models
ollama pull llama3:8b
ollama pull llama2
ollama pull mistral
```

**Check installed models:**
```bash
ollama list
```

## 🚀 Setup Instructions

### Step 1: Update Your .env File

Create or update `.env` in the project root:

```bash
# Ollama Configuration
# Use system Ollama instead of containerized version
OLLAMA_MODEL=gemma2:2b
OLLAMA_BASE_URL=http://host.docker.internal:11434

# ChromaDB Configuration
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# LangSmith was removed. Do not set telemetry keys.
```

### Step 2: Stop Existing Containers

```bash
docker compose down
```

### Step 3: Start Services

```bash
# Rebuild and start (only ChromaDB and RAG API)
docker compose up --build -d

# Check status
docker compose ps
```

You should see only 2 services running:
- `chromadb_service`
- `rag_api_service`

### Step 4: Verify Connection

```bash
# Check system status
curl http://localhost:8001/system/status | jq '.llm'
```

Expected output:
```json
{
  "status": "online",
  "available": true,
  "model_configured": "gemma2:2b",
  "model_available": true,
  "models_installed": ["gemma2:2b", ...],
  "response_time_ms": 8.5
}
```

### Step 5: Test the Chatbot

Open your browser:
```
http://localhost:8001
```

The LLM status card should show:
- **Status:** Ready
- **Model:** Ollama · gemma2:2b
- **Traffic Light:** Green ✅

## 🎯 Benefits of Using System Ollama

### 1. **Better Performance**
- Direct access to system GPU/CPU
- No Docker overhead
- Faster model loading
- Lower latency

### 2. **Easier Model Management**
- Use `ollama pull` directly from terminal
- Models shared across all projects
- No need to download models into Docker volume

### 3. **Resource Efficiency**
- Less memory usage (no duplicate models)
- Better GPU utilization
- Faster startup times

### 4. **Development Workflow**
- Test models outside Docker
- Easier debugging
- Use Ollama CLI tools directly

## 🔧 Troubleshooting

### Problem: "Connection refused" to Ollama

**Solution:**
```bash
# 1. Check if Ollama is running
curl http://localhost:11434/api/tags

# 2. If not running, start it
ollama serve

# 3. On macOS, you can also use:
brew services start ollama
```

### Problem: "Model not found"

**Solution:**
```bash
# List installed models
ollama list

# Pull the model you need
ollama pull gemma2:2b
```

### Problem: Docker can't reach host Ollama

**Solution:**

On **Linux**, you may need to use a different URL:
```bash
# Update .env file
OLLAMA_BASE_URL=http://172.17.0.1:11434
```

Or use host network mode in docker-compose.yml:
```yaml
rag-api:
  network_mode: "host"
```

### Problem: Slow responses

**Solution:**
```bash
# 1. Check Ollama logs
ollama serve

# 2. Monitor system resources
top

# 3. Try a smaller model
ollama pull gemma2:2b  # Only 1.6 GB
```

## 📊 Performance Comparison

| Metric | Docker Ollama | System Ollama |
|--------|---------------|---------------|
| **First Query** | 15-30s | 5-10s |
| **Subsequent Queries** | 3-5s | 1-2s |
| **Memory Usage** | Higher (duplicate models) | Lower (shared models) |
| **GPU Access** | Limited | Direct |
| **Model Loading** | Slower | Faster |

## 🔄 Switching Back to Docker Ollama

If you want to switch back to containerized Ollama:

1. **Restore docker-compose.yml:**
   ```bash
   git checkout docker-compose.yml
   ```

2. **Update .env:**
   ```bash
   OLLAMA_BASE_URL=http://ollama:11434
   ```

3. **Restart services:**
   ```bash
   docker compose down
   docker compose up --build -d
   ```

## 📝 Advanced Configuration

### Using a Remote Ollama Instance

You can also connect to a remote Ollama server:

```bash
# In .env file
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

### Running Ollama on a Different Port

```bash
# Start Ollama on custom port
OLLAMA_HOST=0.0.0.0:11435 ollama serve

# Update .env
OLLAMA_BASE_URL=http://host.docker.internal:11435
```

### Multiple Ollama Instances

You can run multiple Ollama instances for different projects:

```bash
# Instance 1 (default)
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Instance 2 (custom)
OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

## ✅ Verification Checklist

- [ ] Ollama installed on system
- [ ] Ollama service running (`ollama serve`)
- [ ] Model downloaded (`ollama pull gemma2:2b`)
- [ ] `.env` file updated with `OLLAMA_BASE_URL`
- [ ] Docker containers rebuilt (`docker compose up --build -d`)
- [ ] Only 2 containers running (chromadb, rag-api)
- [ ] System status shows LLM online
- [ ] Chatbot interface loads successfully
- [ ] Test query completes successfully

## 🎉 Summary

You're now using your system's Ollama installation for better performance! The RAG API container connects to your host Ollama via `host.docker.internal:11434`, giving you:

- ✅ Faster responses
- ✅ Better resource utilization
- ✅ Easier model management
- ✅ Direct GPU access
- ✅ Shared models across projects

**Enjoy the improved performance!** 🚀

