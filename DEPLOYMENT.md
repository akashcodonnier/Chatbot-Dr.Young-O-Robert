# 🚀 Deployment Guide

## Quick Start

### Local Testing (Ollama)
```bash
# No setup needed! Just run:
python unified_server.py

# Visit: http://localhost:8000
```

---

## 🌐 Cloud Deployment Options

Cloud deployment options have been removed since Groq has been removed from this version.
This project now only supports local deployment using Ollama.

### Local Deployment Only

**Step 1: Install Ollama**
1. Visit: https://ollama.ai
2. Download and install Ollama for your operating system
3. Start Ollama service

**Step 2: Run the Application**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run server
python unified_server.py

# Visit: http://localhost:8000
```

---

## 🔧 How It Works

### Local LLM Inference Only

The app now uses only local LLM inference:

**Local Development:**
```
Uses Ollama (localhost:11434)
✓ Ollama must be running
✓ Model: llama2:latest
```

---

## 🗄️ Database Options

### Local Development
```python
# Uses localhost MySQL automatically
# No configuration needed
```

### Cloud with External MySQL
```
Set these environment variables:

DB_HOST = your_mysql_host
DB_USER = your_mysql_user
DB_PASSWORD = your_mysql_password
DB_NAME = case_studies_db
```

---

## ❓ Troubleshooting

### Ollama Error (Local)
```
Error: Cannot connect to Ollama service
```
**Solution:** Start Ollama: `ollama serve`

### Database Error
```
Error: Can't connect to MySQL server
```
**Solution:**
- Local: Make sure MySQL is running
- Cloud: Check DB_* environment variables

---

## 📞 Support

- Ollama Docs: https://ollama.ai/docs
- FastAPI Docs: https://fastapi.tiangolo.com/

---

## 🎯 Performance

| Metric | Ollama (Local) |
|--------|----------------|
| **Speed** | 10-15s |
| **Model** | llama2:7B |
| **Quality** | Good |
| **Cost** | Free |
| **24/7** | No (PC must be on) |

---

Made with ❤️ for Dr. Robert Young's Semantic Search
