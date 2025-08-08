from flask import Flask, request, jsonify
from decision_engine import decide
from document_parser import parse_document
from query_parser import parse_query
from retriever import build_vector_index, search

app = Flask(__name__)

# Health check route
@app.route("/")
def home():
    return jsonify({"status": "✅ API is running on Vercel"})

@app.route("/upload", methods=["POST"])
def upload_document():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    chunks = parse_document(file)
    index, stored_chunks = build_vector_index(chunks)
    return jsonify({"message": "Document processed", "chunks": len(stored_chunks)})

@app.route("/query", methods=["POST"])
def query_document():
    data = request.json
    query = data.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400
    parsed_query = parse_query(query)
    # NOTE: In-memory demo only; index/chunks should be managed better for real use
    chunks = ["Example chunk 1", "Example chunk 2"]  
    index, stored_chunks = build_vector_index(chunks)
    results = search(parsed_query, index, stored_chunks)
    decision = decide(results)
    return jsonify({"decision": decision, "results": results})

# No `if __name__ == "__main__"` needed for Vercel
