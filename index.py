from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import re
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import smtplib
from email.message import EmailMessage

# Import your existing helper modules
from document_parser import extract_text_from_pdf, extract_text_from_docx, chunk_text
from retriever import build_vector_index, search
from query_parser import parse_query
from decision_engine import evaluate_decision

app = Flask(__name__)

# ---------- Database Setup ----------
    os.makedirs("logs", exist_ok=True)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            query TEXT,
            parsed TEXT,
            clauses TEXT,
            decision TEXT
        )
    ''')
    conn.commit()
    conn.close()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO decisions (timestamp, query, parsed, clauses, decision)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, query, json.dumps(parsed), json.dumps(clauses), json.dumps(decision)))
    conn.commit()
    conn.close()

# ---------- Utility Functions ----------
def generate_pdf(query, parsed, clauses, decision):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = [Paragraph("📑 Insurance Decision Report", styles["Title"]), Spacer(1, 12)]
    elements.append(Paragraph(f"📝 Query: {query}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("🔍 Parsed Query:", styles["Heading2"]))
    for k, v in parsed.items():
        elements.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Retrieved Clauses:", styles["Heading2"]))
    for c in clauses:
        elements.append(Paragraph(c, styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📌 Final Decision:", styles["Heading2"]))
    for k, v in decision.items():
        elements.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    doc.build(elements)
    buffer.seek(0)
    return buffer

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_USER")
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_PASSWORD"))
        smtp.send_message(msg)

def extract_json_from_text(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

# ---------- API Endpoints ----------
@app.route("/")
def home():
    return jsonify({"message": "LLM Insurance Decision API is running"})

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    suffix = os.path.splitext(file.filename)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        file_path = tmp.name

    # Extract & index document
    text = extract_text_from_pdf(file_path) if suffix == ".pdf" else extract_text_from_docx(file_path)
    chunks = chunk_text(text)
    build_vector_index(chunks)

    return jsonify({"message": "File processed and indexed successfully"}), 200

@app.route("/query", methods=["POST"])
def process_query():
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    parsed = parse_query(query)
    if "error" in parsed:
        return jsonify({"error": "Failed to parse query"}), 400

    retrieved = search(query)
    clause_chunks = [f"[Chunk {i}] {chunk}" for i, chunk in retrieved]
    decision = evaluate_decision(parsed, clause_chunks)
    decision_json = extract_json_from_text(decision)

    if not decision_json:
        return jsonify({"error": "Could not parse decision JSON", "raw": decision}), 500

    timestamp = datetime.now().isoformat()

    return jsonify({
        "timestamp": timestamp,
        "query": query,
        "parsed": parsed,
        "retrieved_clauses": clause_chunks,
        "decision": decision_json
    })

@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    data = request.get_json()
    pdf_buffer = generate_pdf(
        data["query"],
        data["parsed"],
        data["retrieved_clauses"],
        data["decision"]
    )
    return send_file(pdf_buffer, as_attachment=True, download_name="insurance_report.pdf", mimetype="application/pdf")

@app.route("/send-email", methods=["POST"])
def api_send_email():
    data = request.get_json()
    try:
        send_email(
            to_email=data["to_email"],
            subject=data["subject"],
            body=data["body"]
        )
        return jsonify({"message": "Email sent successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- Run App ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
