
# Blog QA System

A question-answering system that scrapes blog posts and answers questions using LLM with advanced features.

## Key Features

### 🧠 Semantic Search
- Vector-based similarity search using sentence transformers
- Contextual understanding of user queries
- Fast and accurate article matching

### 💬 Conversational AI
- Session-based memory for context awareness
- Follow-up question support with conversation history
- Streaming responses for real-time interaction

### ⚡ Performance Optimized
- Fast embedding generation with all-MiniLM-L6-v2
- Efficient database queries with indexing
- Streaming LLM responses for immediate feedback

### 🔧 Developer Friendly
- Modular architecture with clear separation of concerns
- Comprehensive logging and error handling
- Easy setup with automated model downloading



## How It Works

### 1. Data Scraping
- The scraper extracts content from specified websites (currently configured for case studies)
- Extracts title, content, URL, date, author, and categories
- Creates vector embeddings using the `all-MiniLM-L6-v2` model
- Stores everything in MySQL database

### 2. Vector Storage
- Content is stored in MySQL with vector embeddings as JSON
- Uses Sentence Transformers for semantic encoding
- Cosine similarity for semantic search

### 3. Chat Interface
- User submits a question
- Question is converted to vector embedding
- System finds top 1 most semantically similar article (optimized for speed)
- References are extracted and sent to TinyLlama for response generation
- Returns AI-generated answer with source references

## Components

### Backend (`backend/main.py`)
- FastAPI server with `/chat` endpoint
- Handles vector similarity search
- Integrates with Ollama for TinyLlama inference (fastest model)
- Comprehensive error handling and detailed timing logs

### Database (`database/db.py`)
- MySQL connection management
- Context manager for proper connection handling

### Scraper (`scraper/scrape_and_embed.py`)
- Web scraping with BeautifulSoup
- Vector embedding generation
- SQL storage with embeddings

## 🚀 Quick Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Download the model** (automatic):
```bash
python download_model.py
```

3. **Download the model** (automatic):
```bash
python download_model.py
```
This will download TinyLlama (fastest model) automatically.

4. **Configure database**:
- Edit `database/db.py` with your MySQL credentials
- Create database: `case_studies_db`

5. **Run the scraper** (first time only):
```bash
python scraper/scrape_and_embed.py
```

6. **Start the server** (choose one):

**Option A - Direct Python** (recommended):
```bash
python backend/main.py
```

**Option B - Uvicorn** (alternative):
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

7. **Access the API**:
- Open http://127.0.0.1:8000/docs for interactive documentation




## ⚡ Performance

**Current Configuration (Fastest)**:
- Model: TinyLlama (1.1B params) - 2-3x faster than Llama2
- Context: 500 characters per article
- Articles: Top 1 match (instead of 2)
- Expected response time: 8-12 seconds

**Previous Configuration**:
- Model: Llama2 (7B params)
- Context: 800 characters
- Articles: Top 2 matches
- Response time: ~21 seconds

## 🛠️ Requirements

- Python 3.8+
- MySQL database
- Ollama (https://ollama.ai)
- Internet connection for scraping

## 📁 Project Structure

```
├── backend/           # FastAPI server
├── database/          # MySQL connection
├── scraper/           # Web scraper
├── download_model.py  # Auto model downloader
└── requirements.txt   # Dependencies
```

## 🌐 API Endpoints

- `GET /` - Health check
- `POST /chat` - Chat endpoint (accepts JSON with `question` field)
- `GET /docs` - Interactive API documentation


## 💡 Example Requests

**Sample Questions to Test**:


## 💡 Performance Tips

**For Faster Responses**:
- Use TinyLlama model (default)
- Reduce context size
- Use fewer reference articles

**For Better Accuracy**:
- Increase similarity threshold
- Use larger context (800+ chars)
- Include more reference articles

## Folder Structure:

├── backend/
│   └── main.py          # Main API server with semantic search
├── database/
│   └── db.py            # Database connection module
├── scraper/
│   └── scrape_and_embed.py  # Web scraper with embedding
├── .gitignore           # Properly ignores temporary/output files
├── README.md            # Setup and usage instructions
├── download_model.py    # Automatic model download/setup
└── requirements.txt     # Dependencies

## Question:

1. How can such a small three-person study prove that MasterPeace Zeolite Z truly removes toxins from the human body?

2. What makes the MasterPeace Zeolite Z formula different from other detox or zeolite products already on the market?

3. If people are constantly exposed to environmental and nano-scale toxins, how can they maintain low levels of these compounds long-term after using the product?

4. What exactly is fog water contamination and why should I care about it?

5. How does MasterPeace Zeolite Z work to protect me from these fog-borne or aerial spraying substances?

6. If I use MasterPeace Zeolite Z, does that mean I don’t need to worry about aerial spraying or fog-water pollution?

7. Why should I be concerned about wireless technologies like 5G or 6G and how they affect my health?

8. What practical steps can I take to protect myself from the possible harmful effects of RF-EMFs?

9. Does detoxification really help in dealing with wireless radiation and nano-material exposures, and if so, how?

---

## 🖥️ Server Commands

**Restart chatbot service:**
```bash
sudo systemctl restart chatbot
```

**View live logs:**
```bash
journalctl -u chatbot -f
```

**ChatBOt Stop Command **
``````sudo systemctl stop chatbot
`````

## 🔐 Server .env Configuration

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=Root@2106db
DB_NAME=case_studies_db
```