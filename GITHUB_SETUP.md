# 🚀 Publishing to Private GitHub Repository

This guide will walk you through publishing your Secure RAG Chatbot to a private GitHub repository.

## 📋 Prerequisites

- GitHub account
- Git installed locally (usually comes with macOS/Linux, download for Windows)
- Your project working locally

## 🔐 Important Security Notes

**Before publishing:**
- ✅ `.env` file is gitignored (contains sensitive configuration)
- ✅ `data/` folder is gitignored (your private documents)
- ✅ `chroma_data/` is gitignored (vector database)
- ✅ Docker volumes and build artifacts are gitignored

**What WILL be published:**
- Source code (Python, JavaScript, HTML, CSS)
- Configuration templates
- Documentation (README, USER_GUIDE)
- Docker configuration files

---

## Step 1: Create a Private GitHub Repository

### Option A: Via GitHub Web Interface

1. **Go to GitHub**: https://github.com
2. **Click** the "+" icon (top-right) → "New repository"
3. **Configure your repository:**
   - **Repository name**: `secure-rag-chatbot` (or your preferred name)
   - **Description**: "Private RAG chatbot with 30+ file format support"
   - **Visibility**: ⚠️ **Select "Private"** (IMPORTANT!)
   - **DO NOT** initialize with README, .gitignore, or license (we have these)
4. **Click** "Create repository"
5. **Copy** the repository URL (you'll need this in Step 3)

### Option B: Via GitHub CLI (gh)

```bash
# Install GitHub CLI if not already installed
# macOS: brew install gh
# Login to GitHub
gh auth login

# Create private repository
gh repo create secure-rag-chatbot --private --description "Private RAG chatbot with 30+ file format support"

# The CLI will give you the repository URL
```

---

## Step 2: Initialize Local Git Repository

Open your terminal and navigate to your project directory:

```bash
cd /Users/comzis/Projects/secure-rag-project

# Initialize git repository
git init

# Add all files (respects .gitignore)
git add .

# Check what will be committed (verify .env is NOT listed)
git status

# Create initial commit
git commit -m "Initial commit: Secure RAG chatbot with 30+ file format support

Features:
- Modern web-based chatbot interface
- Support for 30+ file formats (PDF, Word, Excel, PowerPoint, code, data files)
- FastAPI backend with LlamaIndex
- ChromaDB vector database
- Ollama for local LLM inference
- Real-time processing status
- Source citations in responses"
```

---

## Step 3: Connect to GitHub and Push

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repository name:

```bash
# Add GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Verify remote was added
git remote -v

# Push to GitHub (creates main branch)
git branch -M main
git push -u origin main
```

### If using SSH instead of HTTPS:

```bash
# Add SSH remote
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Authentication

**First time pushing?** GitHub will prompt for authentication:

**Option 1: Personal Access Token (Recommended)**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Use the token as your password when prompted

**Option 2: SSH Key**
1. Generate SSH key: `ssh-keygen -t ed25519 -C "your_email@example.com"`
2. Add to GitHub: Settings → SSH and GPG keys → New SSH key
3. Copy your public key: `cat ~/.ssh/id_ed25519.pub`

---

## Step 4: Verify Your Repository

1. **Go to your GitHub repository**: https://github.com/YOUR_USERNAME/YOUR_REPO_NAME
2. **Verify files are present:**
   - ✅ README.md
   - ✅ USER_GUIDE.md
   - ✅ docker-compose.yml
   - ✅ app/ directory
   - ✅ .gitignore
   - ❌ .env (should NOT be visible)
   - ❌ data/ contents (should be empty except .gitkeep)
   - ❌ chroma_data/ (should NOT be visible)

3. **Check repository is private:**
   - Look for "Private" badge next to repository name
   - Settings → General → scroll to "Danger Zone" → verify "Change repository visibility" shows "Private"

---

## Step 5: Clone on Another Machine (Optional)

To use your chatbot on another computer:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME

# Create .env file (NOT tracked by git)
cat > .env << EOF
OLLAMA_MODEL=llama2
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF

# Start services
docker compose up --build -d

# Download model
docker exec ollama_service ollama pull llama2

# Open browser to http://localhost:8001
```

---

## 📝 Future Updates

### Making Changes and Pushing Updates

```bash
# Check what changed
git status

# View differences
git diff

# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add support for additional file formats"

# Push to GitHub
git push
```

### Best Practices

1. **Commit frequently** with clear messages
2. **Never commit** `.env` file or sensitive data
3. **Use branches** for experimental features:
   ```bash
   git checkout -b feature/new-ui
   # Make changes...
   git commit -am "Update chatbot UI"
   git push -u origin feature/new-ui
   # Create Pull Request on GitHub
   ```

4. **Pull before pushing** if working from multiple locations:
   ```bash
   git pull origin main
   git push
   ```

---

## 🔒 Repository Access Management

### Invite Collaborators (if needed)

1. Go to repository → Settings → Collaborators and teams
2. Click "Add people"
3. Enter GitHub username or email
4. Select permission level:
   - **Read**: Can view and clone
   - **Write**: Can push changes
   - **Admin**: Full access

### Repository Settings

**Recommended settings for private repositories:**

1. **Settings → General:**
   - ✅ "Disable" wiki (unless needed)
   - ✅ "Disable" projects (unless needed)
   - ✅ "Allow merge commits"

2. **Settings → Branches:**
   - Consider adding branch protection for `main`
   - Require pull request reviews before merging

3. **Settings → Security:**
   - Enable Dependabot alerts
   - Enable Dependabot security updates

---

## 🚨 Troubleshooting

### Problem: `.env` file was committed by mistake

```bash
# Remove from git but keep locally
git rm --cached .env

# Add to .gitignore (should already be there)
echo ".env" >> .gitignore

# Commit the removal
git commit -m "Remove .env from git tracking"
git push

# Note: The file is still in git history
# To completely remove from history (advanced):
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all
git push origin --force --all
```

### Problem: Repository is public by mistake

1. Go to Settings → General
2. Scroll to "Danger Zone"
3. Click "Change visibility" → "Make private"

### Problem: Large files or folders committed

```bash
# Check repository size
du -sh .git

# Remove large files
git rm -r --cached chroma_data/
git commit -m "Remove large data files"
git push
```

### Problem: Push rejected

```bash
# Pull latest changes first
git pull origin main --rebase

# Resolve any conflicts
# Then push
git push
```

---

## 📚 Additional Resources

- [GitHub Docs: Creating a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories)
- [Git Documentation](https://git-scm.com/doc)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

## ✅ Checklist

Before pushing to GitHub:

- [ ] `.gitignore` is configured correctly
- [ ] `.env` file is gitignored
- [ ] `data/` folder is gitignored (except `.gitkeep`)
- [ ] `chroma_data/` is gitignored
- [ ] Repository is set to **Private** on GitHub
- [ ] README.md is informative
- [ ] All sensitive data removed from code
- [ ] Tested that project works after cloning

After pushing:

- [ ] Verified repository is private on GitHub
- [ ] Checked that `.env` is NOT visible on GitHub
- [ ] README renders correctly
- [ ] All necessary files are present
- [ ] Tested cloning and running on fresh environment (optional but recommended)

---

**Your private RAG chatbot is now safely stored on GitHub!** 🎉

