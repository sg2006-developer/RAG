# app.py
from flask import Flask, request, jsonify, render_template, send_from_directory
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import joblib
import requests
import os
import logging

app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(level=logging.INFO)

# ------------------ CONFIG — edit these as needed ------------------
EMBEDDINGS_FILE = "embeddings.joblib"         # <-- path to your embeddings.joblib
OLLAMA_BASE = "http://localhost:11434/api"    # <-- Ollama / LLM API base
EMBED_MODEL = "bge-m3"                        # <-- embedding model
GEN_MODEL = "llama3.2"                        # <-- generation model
TOP_K = 6                                     # <-- how many similar chunks to send to LLM
VIDEO_URL_BASE = ""                           # <-- optional: base URL for clickable video links, e.g. "https://videos.example.com/watch?v="
# ------------------------------------------------------------------

# Validate embeddings file presence early
if not os.path.exists(EMBEDDINGS_FILE):
    raise FileNotFoundError(f"{EMBEDDINGS_FILE} not found in {os.getcwd()}")

# Load embeddings DataFrame — expected columns: ['title','number','start','end','text','embedding']
df = joblib.load(EMBEDDINGS_FILE)

def create_embedding(text_list):
    """Call Ollama embed endpoint. Returns list of embeddings."""
    r = requests.post(f"{OLLAMA_BASE}/embed", json={
        "model": EMBED_MODEL,
        "input": text_list
    }, timeout=30)
    r.raise_for_status()
    return r.json().get("embeddings", [])

def inference(prompt):
    """Call Ollama generate endpoint. Returns model JSON."""
    r = requests.post(f"{OLLAMA_BASE}/generate", json={
        "model": GEN_MODEL,
        "prompt": prompt,
        "stream": False
    }, timeout=60)
    r.raise_for_status()
    return r.json()

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # 1. Create embedding
    try:
        q_emb = create_embedding([message])[0]
    except Exception as e:
        app.logger.exception("Embedding error")
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500

    # 2. Compute similarities
    try:
        all_emb = np.vstack(df['embedding'].values)
        sims = cosine_similarity(all_emb, [q_emb]).flatten()
    except Exception as e:
        app.logger.exception("Similarity error")
        return jsonify({"error": f"Similarity computation failed: {str(e)}"}), 500

    # 3. Get top-k matches
    top_idx = sims.argsort()[::-1][:TOP_K]
    matches = df.iloc[top_idx].copy()
    matches['score'] = sims[top_idx]

    # 4. Build prompt for the LLM
    extracted = matches[["title", "number", "start", "end", "text", "score"]].to_json(orient="records")
    prompt = f"""They are teaching web development in their web development course. Here are video subtitle chunks containing video title, video number, start time in seconds, end time in seconds, the text at that time:

{extracted}
---------------------------------
\"{message}\"
User asked this question related to the video chunks, you have to answer in a human way (dont mention the above format, its just for you) where and how much content is taught in which video (in which video and at what timestamp) and guide the user to go to that particular video. If user asks unrelated question, tell him that you can only answer questions related to the course
"""
    # optional debug save
    try:
        with open("prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception:
        pass

    # 5. Call generator
    try:
        resp = inference(prompt)
        # Extract text from common keys
        if isinstance(resp, dict):
            answer = resp.get("response") or resp.get("text") or resp.get("output") or str(resp)
        else:
            answer = str(resp)
    except Exception as e:
        app.logger.exception("Inference error")
        return jsonify({"error": f"Inference failed: {str(e)}"}), 500

    # optional debug save
    try:
        with open("response.txt", "w", encoding="utf-8") as f:
            f.write(str(answer))
    except Exception:
        pass

    # 6. Build sources for frontend
    sources = []
    for _, row in matches.iterrows():
        video_link = None
        if VIDEO_URL_BASE and row.get("number") is not None:
            # Customize if your video links are different
            video_link = f"{VIDEO_URL_BASE}{row['number']}#t={int(row['start'])}"
        sources.append({
            "title": str(row.get("title", "")),
            "number": str(row.get("number", "")),
            "start": float(row.get("start", 0.0)),
            "end": float(row.get("end", 0.0)),
            "snippet": str(row.get("text", ""))[:300],
            "score": float(row.get("score", 0.0)),
            "video_link": video_link
        })

    return jsonify({"answer": answer, "sources": sources})

# Serve static (Flask normally does this, but explicit route included)
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    # Edit host/port here if you want
    app.run(host="0.0.0.0", port=5000, debug=True)
