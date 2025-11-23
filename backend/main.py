from dotenv import load_dotenv
load_dotenv()

import io
import os
import uuid
from datetime import datetime, UTC
from flask import Flask, request, send_file, jsonify, Response
from flask_cors import CORS

# Local modules
from db import init_db, create_conversation, get_conversation, delete_conversation, insert_message, get_messages
from claude import build_trimmed_history, call_haiku
from redis_queue import enqueue_job, get_job
from tts import synthesize_bytes, synthesize_stream, STREAM_THRESHOLD_CHARS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration
DATA_DB_PATH = os.environ.get("DATA_DB_PATH", "data.db")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "5000"))
TOKEN_BUDGET = int(os.environ.get("TOKEN_BUDGET", "8192"))

# Initialize DB
init_db(DATA_DB_PATH)

# Helpers
def now_iso():
    return datetime.now(UTC).isoformat() + "Z"

# @app.route("/health", methods=["GET"])
# def health():
#     # Basic health check
#     db_ok = True
#     redis_ok = True
#     try:
#         # quick DB read
#         _ = get_conversation("non-existent-id")
#     except Exception:
#         db_ok = False
#     try:
#         _ = get_job("non-existent-job-id")
#     except Exception:
#         # get_job may raise if Redis not available
#         redis_ok = False
#     status = {"status": "ok" if db_ok and redis_ok else "degraded", "db": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"}
#     return jsonify(status)

@app.route('/conversations', methods=['POST'])
def create_conversation_endpoint():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get('user_id')
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
    conv_id = create_conversation(user_id=user_id, metadata=metadata)
    return jsonify({"conversation_id": conv_id, "created_at": now_iso()}), 201

@app.route('/conversations/<conversation_id>', methods=['GET'])
def get_conversation_endpoint(conversation_id):
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "not found"}), 404
    return jsonify(conv)

@app.route('/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation_endpoint(conversation_id):
    deleted = delete_conversation(conversation_id)
    if not deleted:
        return jsonify({"error": "not found"}), 404
    return ('', 204)

@app.route('/conversations/<conversation_id>/messages', methods=['GET'])
def list_messages_endpoint(conversation_id):
    since = request.args.get('since')
    limit = int(request.args.get('limit', '100'))
    messages = get_messages(conversation_id, since=since, limit=limit)
    return jsonify({"messages": messages})

@app.route('/conversations/<conversation_id>/messages', methods=['POST'])
def post_message_endpoint(conversation_id):
    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400
    payload = request.get_json()
    role = payload.get('role', 'user')
    content = payload.get('content')
    response_mode = payload.get('response_mode', 'sync')
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}

    if not content or not isinstance(content, str) or not content.strip():
        return jsonify({"error": "content is required"}), 400
    if len(content) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    # persist caller message
    msg_id = insert_message(conversation_id=conversation_id, role=role, content=content, metadata=metadata)

    # For sync responses, call Claude Haiku immediately (trimmed)
    if response_mode == 'sync':
        history = build_trimmed_history(conversation_id, token_budget=TOKEN_BUDGET)
        try:
            assistant_text = call_haiku(history)
        except Exception as e:
            return jsonify({"error": "assistant call failed", "detail": str(e)}), 500
        # persist assistant reply
        assistant_id = insert_message(conversation_id=conversation_id, role='assistant', content=assistant_text, metadata={})
        assistant_msg = {
            "id": assistant_id,
            "role": "assistant",
            "content": assistant_text,
            "created_at": now_iso(),
            "metadata": {}
        }
        return jsonify({"assistant_message": assistant_msg}), 200
    else:
        # async: enqueue a long_response job
        job = {
            "job_id": str(uuid.uuid4()),
            "type": "long_response",
            "conversation_id": conversation_id,
            "message_id": msg_id,
            "payload": {"trigger_message_id": msg_id, "response_mode": "text"},
            "created_at": now_iso()
        }
        enqueue_job(job)
        # create placeholder assistant message with pending status
        placeholder_id = insert_message(conversation_id=conversation_id, role='assistant', content='', metadata={"status": "pending", "job_id": job["job_id"]})
        return jsonify({"job_id": job["job_id"], "placeholder_message_id": placeholder_id}), 202

@app.route('/conversations/<conversation_id>/tts', methods=['POST'])
def tts_endpoint(conversation_id):
    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400
    payload = request.get_json()
    message_id = payload.get('message_id')
    text = payload.get('text')
    voice = payload.get('voice')
    response_mode = payload.get('response_mode', 'sync')

    if message_id:
        msgs = get_messages(conversation_id, limit=1000)
        message = next((m for m in msgs if m['id'] == message_id), None)
        if not message:
            return jsonify({"error": "message_id not found"}), 404
        text_to_speak = message['content']
    else:
        if not text or not isinstance(text, str) or not text.strip():
            return jsonify({"error": "text is required when message_id is not provided"}), 400
        text_to_speak = text

    if len(text_to_speak) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    if response_mode == 'sync':
        # choose convert() for small text, stream() for large
        try:
            if len(text_to_speak) <= STREAM_THRESHOLD_CHARS:
                audio_bytes = synthesize_bytes(text_to_speak)
                buf = io.BytesIO(audio_bytes)
                buf.seek(0)
                return send_file(buf, mimetype='audio/mpeg', as_attachment=False)
            else:
                # stream generator
                def generate():
                    for chunk in synthesize_stream(text_to_speak):
                        yield chunk
                return Response(generate(), mimetype='audio/mpeg')
        except Exception as e:
            return jsonify({"error": "TTS generation failed", "detail": str(e)}), 500
    else:
        # async: enqueue tts job
        job = {
            "job_id": str(uuid.uuid4()),
            "type": "tts",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "payload": {"text": text_to_speak, "voice": voice},
            "created_at": now_iso()
        }
        enqueue_job(job)
        return jsonify({"job_id": job["job_id"]}), 202


@app.route('/conversations/<conversation_id>/tts_stream', methods=['POST','GET'])
def tts_stream_endpoint(conversation_id):
    """Stream TTS audio bytes to the client as they are generated.
    For POST: accept JSON { "message_id"?: str, "text"?: str, "voice"?: str }.
    For GET: accept query params ?message_id=... or ?text=...&voice=...
    Response: chunked audio/mpeg stream (suitable for <audio src="..."> playback)
    """
    # Support both POST (JSON body) and GET (query string) for streaming URL usage
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "expected JSON body"}), 400
        payload = request.get_json()
        message_id = payload.get('message_id')
        text = payload.get('text')
        voice = payload.get('voice')
    else:
        # GET
        message_id = request.args.get('message_id')
        text = request.args.get('text')
        voice = request.args.get('voice')

    if message_id:
        msgs = get_messages(conversation_id, limit=1000)
        message = next((m for m in msgs if m['id'] == message_id), None)
        if not message:
            return jsonify({"error": "message_id not found"}), 404
        text_to_speak = message['content']
    else:
        if not text or not isinstance(text, str) or not text.strip():
            return jsonify({"error": "text is required when message_id is not provided"}), 400
        text_to_speak = text

    if len(text_to_speak) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    try:
        # Return a streaming response the browser can play via <audio src="..."> (GET)
        # Use direct_passthrough so Flask/Werkzeug doesn't buffer the iterable
        resp = Response(synthesize_stream(text_to_speak), mimetype='audio/mpeg', direct_passthrough=True)
        # Avoid setting Content-Length so Transfer-Encoding: chunked is used
        # Advise proxies not to buffer the response
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        resp.headers['Connection'] = 'keep-alive'
        return resp
    except Exception as e:
        return jsonify({"error": "TTS streaming failed", "detail": str(e)}), 500

@app.route('/jobs/<job_id>', methods=['GET'])
def get_job_endpoint(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job)

@app.route('/conversations/<conversation_id>/export', methods=['GET'])
def export_conversation(conversation_id):
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "not found"}), 404
    messages = get_messages(conversation_id, limit=10000)
    return jsonify({"conversation": conv, "messages": messages})

@app.route('/')
def index():
    # Serve the single-file frontend from the same origin to avoid CORS/file:// issues
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(path):
        return send_file(path)
    return jsonify({"error": "index.html not found"}), 404

@app.route('/record')
def index():
    path = os.path.join(os.path.dirname(__file__), 'record.html')
    if os.path.exists(path):
        return send_file(path)
    return jsonify({"error": "record.html not found"}), 404

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
