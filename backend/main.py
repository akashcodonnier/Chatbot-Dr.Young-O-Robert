#!/usr/bin/env python3
"""
Backend API for Dr. Robert Young's semantic search Q&A system

This module provides a FastAPI application that:
1. Performs semantic search on scraped blog articles
2. Generates contextual answers using local LLM
3. Provides performance timing information
"""

# Standard library imports
import sys
import os
import time
import re
import ast
import json
import subprocess
import numpy as np
from collections import deque
import asyncio

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Third-party imports
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
from sentence_transformers import SentenceTransformer

# Using only local Ollama for LLM
print("[INFO] Using only Ollama (local mode).")

# Local imports
# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
from database.db import get_connection

# Initialize FastAPI app
app = FastAPI(
    title="Dr. Robert Young Semantic Search API",
    description="Semantic search and Q&A system for Dr. Robert Young's blog content",
    version="1.0.0"
)

# Initialize embedding model for vector search
import torch
import warnings
import logging
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

device = "cpu"
print("[MODEL] Loading embedding model (from local cache)...")
embed_model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    device=device
)
print("[MODEL] Embedding model ready!")

print("[LLM] Using Ollama (Local mode)")

# Session-based conversation memory (stores last 5 interactions per conversation)
conversation_memory = {}

# ─── Embedding Cache ───────────────────────────────────────────────────────────
# Load all article embeddings into memory at startup (fast in-memory search)
article_cache = []  # List of dicts: {id, title, url, embedding (numpy array)}

def load_article_cache():
    """Load all article embeddings from DB into memory at startup"""
    global article_cache
    try:
        print("\n[CACHE] Loading article embeddings into memory...")
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, title, url, content, category, published_date, embedding FROM dr_young_all_articles")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        new_cache = []
        for r in rows:
            try:
                emb = np.array(ast.literal_eval(r["embedding"]))
                new_cache.append({
                    "id": r["id"],
                    "title": r["title"],
                    "url": r["url"],
                    "content": r["content"],
                    "category": r["category"],
                    "published_date": r["published_date"],
                    "embedding": emb
                })
            except Exception:
                continue
        article_cache = new_cache  # Atomic swap
        print(f"[CACHE] Loaded {len(article_cache)} articles into memory!")
    except Exception as e:
        print(f"[CACHE] Failed to load cache: {e}")

# Load cache at startup in background
import threading
threading.Thread(target=load_article_cache, daemon=True).start()
# ──────────────────────────────────────────────────────────────────────────────


def warm_up_ollama_model():
    """
    Warm up the Ollama model by making a simple request
    This pre-loads the model into memory to avoid delays on first user request
    """
    try:
        print("\n[OLLAMA] Warming up model...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:latest",        # Use llama3.2 for better accuracy
                "prompt": "Hello",
                "stream": True
            },
            timeout=60
        )
        if response.status_code == 200:
            print("[OLLAMA] Model warmed up successfully!")
        else:
            print(f"[OLLAMA] Warm-up returned status {response.status_code}")
    except Exception as e:
        print(f"[OLLAMA] Warm-up failed: {e}")
        print("[OLLAMA] Model will load on first request (may take 10-15 seconds)")


# Warm up model on startup (run in background to not block server start)
threading.Thread(target=warm_up_ollama_model, daemon=True).start()

def get_conversation_history(conversation_id: str):
    """Get conversation history for given ID"""
    if conversation_id not in conversation_memory:
        conversation_memory[conversation_id] = deque(maxlen=5)
    return conversation_memory[conversation_id]

def add_to_conversation_history(conversation_id: str, question: str, answer: str):
    """Add interaction to conversation history"""
    history = get_conversation_history(conversation_id)
    history.append({
        "question": question,
        "answer": answer,
        "timestamp": time.time()
    })
    
    # Log the addition
    print(f"[SAVED] Session [{conversation_id}]:")
    print(f"   Question: {question[:60]}...")
    print(f"   Answer: {answer[:60]}...")
    print(f"   Total interactions: {len(history)}")


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint
    
    Attributes:
        question (str): The user's question to be answered
        conversation_id (str): Optional conversation identifier to maintain context
    """
    question: str
    conversation_id: str = "default"


def cosine(a, b):
    """
    Calculate cosine similarity between two vectors
    
    Args:
        a (numpy.ndarray): First vector
        b (numpy.ndarray): Second vector
        
    Returns:
        float: Cosine similarity score between 0 and 1
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def clean_context(text: str) -> str:
    """
    Clean and preprocess context text for LLM consumption
    
    This function removes unwanted formatting elements that might confuse the LLM.
    
    Args:
        text (str): Raw text content to be cleaned
        
    Returns:
        str: Cleaned text ready for LLM processing
    """
    # Remove numbered points like "1.", "2)"
    text = re.sub(r"\n?\s*\d+[\.]\)\s*", " ", text)

    # Remove bullet symbols
    text = re.sub(r"[•\-–▪]", " ", text)

    # Remove standalone reference sections at the end (but keep inline URLs and references)
    text = re.sub(r"\n\s*References?\s*:\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    # Normalize spelling of Zeolite (remove accents)
    text = text.replace("Zeolité", "Zeolite")

    return text.strip()




def call_llama2_stream(prompt: str):
    """
    Call locally running LLM via Ollama with streaming capability

    This function establishes a streaming connection to the Ollama service
    and yields response chunks as they become available, enabling real-time
    response delivery to the client.

    Args:
        prompt (str): Formatted prompt including context and question

    Yields:
        str: Response chunks from the LLM as they are generated

    Raises:
        Exception: If connection to Ollama fails or streaming encounters errors
    """
    try:
        # Establish streaming POST request to Ollama API
        with requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:latest",         # Use llama3.2 for better accuracy
                "prompt": prompt,                   # Complete prompt with context
                "stream": True,                     # Enable streaming mode
                "options": {
                    "temperature": 0.1,             # Low temperature for factual accuracy
                    "top_p": 0.9,                   # Nucleus sampling parameter
                    "repeat_penalty": 1.2,          # Penalize repeated tokens
                    "num_predict": 800              # Maximum tokens to generate
                }
            },
            stream=True,                            # Enable response streaming
            timeout=300                             # 5-minute timeout for long responses
        ) as r:

            if r.status_code != 200:
                # Log detailed error for debugging
                error_text = r.text if hasattr(r, 'text') else 'No error details'
                print(f"[OLLAMA ERROR] Status {r.status_code}: {error_text}")
                yield f"[LLM ERROR]: Ollama returned status {r.status_code}. The model may be loading. Please wait a moment and try again."
                return

            # Track if we received any response
            received_response = False

            # Process streaming response line by line
            for line in r.iter_lines():
                if not line:
                    continue

                try:
                    # Parse JSON response chunk
                    data = json.loads(line.decode("utf-8"))

                    # Yield response content if available
                    if "response" in data and data["response"]:
                        received_response = True
                        chunk = data["response"].replace("Zeolité", "Zeolite")
                        yield chunk

                    # Stop streaming when generation is complete
                    if data.get("done"):
                        break

                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
                except Exception as e:
                    yield f"[PARSING ERROR]: {str(e)}"
                    break

            # If no response was received, model might be loading
            if not received_response:
                yield "[LLM ERROR]: No response received. The model may still be loading. Please try again."

    except requests.exceptions.ConnectionError:
        yield "[LLM ERROR]: Cannot connect to Ollama service. Is it running? Start it with 'ollama serve'"
    except requests.exceptions.Timeout:
        yield "[LLM ERROR]: Ollama request timed out. The model may be loading or the prompt may be too complex."
    except Exception as e:
        # Handle streaming errors gracefully
        print(f"[OLLAMA EXCEPTION]: {type(e).__name__}: {str(e)}")
        yield f"[LLM ERROR]: {type(e).__name__} - {str(e)}"


def call_llama2_stream_direct(prompt: str):
    """
    Call locally running LLM via Ollama with streaming capability for direct responses

    This function establishes a streaming connection to the Ollama service
    and yields response chunks as they become available.

    Args:
        prompt (str): Formatted prompt including context and question

    Yields:
        str: Response chunks from the LLM as they are generated

    Raises:
        Exception: If connection to Ollama fails or streaming encounters errors
    """
    try:
        # Establish streaming POST request to Ollama API
        with requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:latest",         # Use llama3.2 for better accuracy
                "prompt": prompt,                   # Complete prompt with context
                "stream": True,                     # Enable streaming mode
                "options": {
                    "temperature": 0.1,             # Low temperature for factual accuracy
                    "top_p": 0.9,                   # Nucleus sampling parameter
                    "repeat_penalty": 1.2,          # Penalize repeated tokens
                    "num_predict": 800              # Maximum tokens to generate
                }
            },
            stream=True,                            # Enable response streaming
            timeout=300                             # 5-minute timeout for long responses
        ) as r:

            # Process streaming response line by line
            for line in r.iter_lines():
                if not line:
                    continue

                # Parse JSON response chunk
                data = json.loads(line.decode("utf-8"))

                # Yield response content if available
                if "response" in data:
                    chunk = data["response"].replace("Zeolité", "Zeolite")
                    yield chunk

                # Stop streaming when generation is complete
                if data.get("done"):
                    break

    except Exception as e:
        # Handle streaming errors gracefully
        yield f"\n[LLM ERROR]: {str(e)}"



@app.post("/chat")
async def chat(q: ChatRequest):
    """
    Main chat endpoint that processes user questions with session-based memory
    
    This endpoint performs semantic search on the blog database, maintains conversation
    context, and generates contextual answers using a local LLM.
    
    Args:
        q (ChatRequest): The user's question request with optional conversation ID
        
    Returns:
        StreamingResponse: Streaming response containing answer and references
    """
    # Start timing for performance measurement
    start_time = time.time()
    
    # Get conversation history
    history = get_conversation_history(q.conversation_id)
    
    # Log conversation tracking
    print(f"[SESSION] CONVERSATION: {q.conversation_id}")
    print(f"[HISTORY] LENGTH: {len(history)} interactions")

    # 1️⃣ Embed user question using sentence transformer
    embed_start = time.time()
    query_emb = embed_model.encode(
        q.question,
        convert_to_numpy=True,
        device="cpu"
    )
    embed_time = time.time() - embed_start

    # 2️⃣ Open DB connection (only for fetching content of top match later)
    db_start = time.time()
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    db_time = time.time() - db_start

    # Prepare list to store similarity scores
    scored = []

    # 3️⃣ Perform vector similarity search using in-memory cache
    search_start = time.time()
    highest_score = 0.0
    for art in article_cache:
        # Calculate cosine similarity with query (embedding already parsed)
        score = cosine(query_emb, art["embedding"])

        # Boost score based on keyword matching in title and content
        skip_words = {"what", "how", "why", "is", "the", "a", "an", "does", "do", "can", "from", "to", "of", "in", "and", "or", "for", "this", "that", "it", "i", "me", "my", "give", "explain", "example", "about", "tell", "mean", "really", "help", "need", "using", "after", "long", "term", "these", "those", "them", "their", "such"}
        meaningful_words = [w for w in q.question.lower().split() if w not in skip_words and len(w) > 2]

        if meaningful_words:
            title_lower = art["title"].lower()
            content_lower = (art.get("content") or "")[:3000].lower()

            # Count how many query words match in title
            title_matches = sum(1 for w in meaningful_words if w in title_lower)
            # Count how many query words match in content
            content_matches = sum(1 for w in meaningful_words if w in content_lower)

            # Title match boost: 0.05 per matching word (max 0.15)
            score += min(title_matches * 0.05, 0.15)
            # Content match boost: 0.02 per matching word (max 0.10)
            score += min(content_matches * 0.02, 0.10)
        
        if score > highest_score:
            highest_score = score

        # Only consider results above threshold (filters out unrelated questions)
        if score > 0.25:
            scored.append((score, art))

    # Sort by similarity score, deduplicate by title, take top 2
    scored = sorted(scored, key=lambda x: x[0], reverse=True)
    seen_titles = set()
    unique_scored = []
    for s, art in scored:
        title_key = art["title"].strip().lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_scored.append((s, art))
        if len(unique_scored) == 2:
            break
    scored = unique_scored
    search_time = time.time() - search_start

    # Log top matches score for debugging
    print(f"[SEARCH] Highest score found: {highest_score:.3f}")
    if scored:
        for i, (score, art) in enumerate(scored, 1):
            print(f"[SEARCH] Match {i}: '{art['title'][:50]}' score={score:.3f}")
    else:
        print(f"[SEARCH] No match above 0.25 for: '{q.question}'")

    # Return if no relevant results found
    if not scored:
        # Generate contextually appropriate response based on question type and conversation context
        question_lower = q.question.lower()
        
        # Case 4: No DB results and no conversation context - Polite refusal
        if not history:
            print(f"[CASE 4] TRIGGERED: No DB match + No conversation history for '{q.question}'")
            general_answer = (
                "I don't have reliable information about this specific topic in the available content. "
                "Could you please provide more details or rephrase your question? "
                "Alternatively, you might want to ask about related topics like general health principles, "
                "wellness practices, or preventive care approaches."
            )
        
        # Case 3: No DB results but continuing previous conversation topic
        elif history:
            # Check if current question relates to previous conversation topics
            # MATCH AGAINST BOTH QUESTION AND ANSWER (as per memory requirement)
            last_interaction = history[-1] if history else {}
            last_question = last_interaction.get('question', '').lower() if last_interaction else ""
            last_answer = last_interaction.get('answer', '').lower() if last_interaction else ""
            
            # Combine question and answer for better context matching
            combined_context = f"{last_question} {last_answer}"
            conversation_keywords = set(combined_context.split())
            current_keywords = set(question_lower.split())
            
            # Calculate keyword overlap
            overlap = len(conversation_keywords.intersection(current_keywords))
            total_unique = len(conversation_keywords.union(current_keywords))
            similarity_ratio = overlap / total_unique if total_unique > 0 else 0
            
            # If there's significant topic continuity (30%+ keyword overlap)
            if similarity_ratio > 0.3 or any(word in question_lower for word in combined_context.split()[:10]):
                print(f"[CASE 3] TRIGGERED: No DB match + Continuing topic ({similarity_ratio:.2f} similarity) for '{q.question}'")
                print(f"   Matching against: Question='{last_question[:50]}...' Answer='{last_answer[:50]}...'")
                
                # CASE 3 LLM FALLBACK - Generate answer using LLM for topic continuity
                # Build context from conversation history for LLM prompt
                llm_prompt = f"""{last_answer[:500]}

Q: {q.question}
A:"""
                
                # Generate answer using LLM for Case 3
                llm_start = time.time()
                
                def stream_case3_response():
                    full_answer = ""

                    # Stream the LLM response chunks as they arrive
                    try:
                        # Call Ollama LLM
                        llm_function = call_llama2_stream_direct
                        for chunk in llm_function(llm_prompt):
                            if chunk.strip():  # Only yield non-empty chunks
                                full_answer += chunk
                                yield chunk
                                time.sleep(0.01)  # Consistent streaming delay
                                
                        # Save conversation AFTER streaming finishes
                        clean_answer = " ".join(full_answer.split())
                        add_to_conversation_history(q.conversation_id, q.question, clean_answer)
                        
                        llm_time = time.time() - llm_start
                        print(f"[TIMING] CASE 3 LLM: {llm_time:.2f}s")
                    except Exception as e:
                        yield f"[LLM ERROR]: {str(e)}"
                
                return StreamingResponse(stream_case3_response(), media_type="text/plain")
                
            else:
                print(f"[CASE 4] TRIGGERED: No DB match + Different topic ({similarity_ratio:.2f} similarity) for '{q.question}'")
                print(f"   Context: Question='{last_question[:50]}...' Answer='{last_answer[:50]}...'")
                # Different topic - Case 4 handling
                general_answer = (
                    "I don't have reliable information about this specific topic in the available content. "
                    "Could you please provide more details or rephrase your question? "
                    "Alternatively, you might want to ask about related topics like general health principles, "
                    "wellness practices, or preventive care approaches."
                )
        
        def stream_general_response():
            # Split the general answer into words or chunks to maintain consistent speed
            words = general_answer.split()
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                time.sleep(0.01)  # Consistent streaming delay
        
        return StreamingResponse(stream_general_response(), media_type="text/plain")

    # 4️⃣ Build context from top matching articles
    context_start = time.time()
    context_parts = []
    references = []  # Track source references with URLs

    for _, art in scored:
        # Add article title and URL to references
        references.append({
            "title": art["title"],
            "url": art["url"]
        })
        # Fetch full content only for top matched article
        cur.execute("SELECT content FROM dr_young_all_articles WHERE id = %s", (art["id"],))
        content_row = cur.fetchone()
        if content_row:
            cleaned = clean_context(content_row["content"])
            context_parts.append(cleaned)

    print(f"\n{'='*60}")
    print(f"[CONTEXT] {len(context_parts)} articles matched:")
    for i, (score, art) in enumerate(scored, 1):
        print(f"  [{i}] Title: {art['title']}")
        print(f"      URL: {art['url']}")
        print(f"      Score: {score:.3f}")
    print(f"{'='*60}")

    # Join all context parts
    context = "\n\n".join(context_parts)
    context_time = time.time() - context_start

    # Log full context being sent to model
    print(f"\n[CONTEXT → MODEL] Total Characters: {len(context)} | Sent to LLM: {len(context[:6000])}")
    print(f"[QUESTION] {q.question}")
    print(f"\n{'─'*60}")
    print(f"[FULL CONTEXT FROM DB]:")
    print(f"{'─'*60}")
    print(context[:6000])
    print(f"{'─'*60}")
    print(f"[END CONTEXT]")
    print(f"{'='*60}")

    # 5️⃣ Format prompt for LLM (strict context-only format)
    prompt = f"""<|system|>
You are a strict Q&A assistant for Dr. Robert O. Young's alkaline lifestyle research.

RULES:
1. ONLY use information from the CONTEXT below. Do NOT add outside knowledge.
2. If context lacks the answer, say: "I don't have enough information based on the available articles."
3. Do NOT invent, guess, or fabricate any facts not in the context.
4. Start your answer directly. No preambles like "Sure!", "Based on the context..." etc.
5. Use professional scientific tone. Be concise and accurate.
6. Use numbered lists (1.) or bullet points (-). Each item on its own line.
7. Always spell "Zeolite" (no accents) and "pH" (lowercase p, uppercase H).
8. CRITICAL: When the context labels something as "FALSE" or a "myth", it means that claim is WRONG. Do NOT present false/myth claims as facts. Instead explain why they are wrong according to the context.
9. Dr. Young PROMOTES the alkaline lifestyle. All answers should reflect his pro-alkaline position as stated in the context.
10. Do NOT recommend fruits, dairy, sugar, or acidic foods as healthy unless the context explicitly says so.
</s>
<|user|>
CONTEXT:
{context[:6000]}

QUESTION: {q.question}
</s>
<|assistant|>"""

    llm_start = time.time()

    def stream_response():

        full_answer = ""

        # Stream the LLM response chunks as they become available
        try:
            # Call Ollama LLM
            llm_function = call_llama2_stream
            for chunk in llm_function(prompt):
                if chunk.strip():
                    chunk = chunk.replace("Zeolité", "Zeolite")
                    full_answer += chunk
                    yield chunk
                    time.sleep(0.01)

            # Extract URLs - Only show the verified source URLs to avoid "junk" or partial links
            unique_references = []
            seen_titles = set()
            
            for ref in references:
                title_clean = ref['title'].strip().lower()
                if title_clean not in seen_titles:
                    unique_references.append(ref)
                    seen_titles.add(title_clean)

            if unique_references:
                yield "\n\nSee here for more info:\n"
                for ref in unique_references:
                    if ref['url']:
                        yield f"- {ref['url']}\n"

                yield "\nReferences:\n"
                for i, ref in enumerate(unique_references, 1):
                    yield f"{i}. {ref['title']}\n"

            # Save conversation AFTER streaming finishes
            clean_answer = " ".join(full_answer.split())
            add_to_conversation_history(q.conversation_id, q.question, clean_answer)
            
            llm_time = time.time() - llm_start
            total_time = time.time() - start_time
            
            print("[TIMING]:")
            print(f"Embedding: {embed_time:.2f}s | DB: {db_time:.2f}s | Search: {search_time:.2f}s")
            print(f"Context: {context_time:.2f}s | LLM: {llm_time:.2f}s | Total: {total_time:.2f}s")
        except Exception as e:
            yield f"[LLM ERROR]: {str(e)}"
        finally:
            try:
                cur.close()
                conn.close()
            except:
                pass

    return StreamingResponse(
        stream_response(),
        media_type="text/plain"
    )
