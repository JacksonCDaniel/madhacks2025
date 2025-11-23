from dotenv import load_dotenv
load_dotenv()

import os
import uuid
from flask import Flask, request, send_file, jsonify, Response
from flask_cors import CORS

# Local modules
from db import init_db, create_conversation, get_conversation, delete_conversation, insert_message, get_messages, now_iso
from claude import build_trimmed_history, call_haiku, stream_haiku
from tts import synthesize_stream
import threading
import queue

# In-memory session store: session_id -> {text_q, audio_q, thread}
SESSIONS = {}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "5000"))
TOKEN_BUDGET = int(os.environ.get("TOKEN_BUDGET", "8192"))

# Initialize DB
init_db()

# Helpers
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
    return '', 204

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
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}

    if not content or not isinstance(content, str) or not content.strip():
        return jsonify({"error": "content is required"}), 400
    if len(content) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    # persist caller message
    msg_id = insert_message(conversation_id=conversation_id, role=role, content=content, metadata=metadata)

    # For sync responses, call Claude Haiku immediately (trimmed)
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

@app.route('/conversations/<conversation_id>/tts', methods=['POST'])
def tts_endpoint(conversation_id):
    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400
    payload = request.get_json()
    message_id = payload.get('message_id')
    text = payload.get('text')

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
        # stream generator
        def generate():
            for chunk in synthesize_stream(text_to_speak):
                yield chunk
        return Response(generate(), mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({"error": "TTS generation failed", "detail": str(e)}), 500

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

@app.route('/conversations/<conversation_id>/export', methods=['GET'])
def export_conversation(conversation_id):
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "not found"}), 404
    messages = get_messages(conversation_id, limit=10000)
    return jsonify({"conversation": conv, "messages": messages})


@app.route('/conversations/<conversation_id>/stream_text')
def stream_text(conversation_id):
    """SSE endpoint that reads from a session's text queue.
    Query param: ?session=<session_id>
    """
    session_id = request.args.get('session')
    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    text_q = SESSIONS[session_id]['text_q']

    def event_stream():
        while True:
            try:
                item = text_q.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                break
            yield f"data: {item}\n\n"

    return Response(event_stream(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache"})


@app.route('/conversations/<conversation_id>/live_audio', methods=['POST','GET'])
def live_audio(conversation_id):
    """POST JSON { "text": "..." } -> streams audio bytes as chunked response by proxying synthesize_stream.
    This is a minimal forwarder that turns text into audio stream for an <audio src=> element.
    """
    # Support GET for session streaming: if GET, expect ?session=<id>
    if request.method == 'GET':
        session_id = request.args.get('session')
        if not session_id:
            return jsonify({"error": "session required for GET"}), 400
        if session_id not in SESSIONS:
            return jsonify({"error": "session not found"}), 404
        audio_q = SESSIONS[session_id]['audio_q']

        def generate_from_queue():
            while True:
                try:
                    data = audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if data is None:
                    break
                yield data

        resp = Response(generate_from_queue(), mimetype='audio/mpeg', direct_passthrough=True)
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        return resp

    # For POST (direct synthesis), expect JSON with 'text'
    session_id = request.args.get('session')
    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400
    payload = request.get_json()
    text = payload.get('text')
    if not text:
        return jsonify({"error": "text required"}), 400

    def generate_direct():
        for chunk in synthesize_stream(text):
            if isinstance(chunk, (bytes, bytearray, memoryview)):
                yield bytes(chunk)
            else:
                yield str(chunk).encode('utf-8')
    resp = Response(generate_direct(), mimetype='audio/mpeg', direct_passthrough=True)
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


@app.route('/conversations/<conversation_id>/start_stream', methods=['POST'])
def start_stream(conversation_id):
    """Start an in-memory streaming session that runs stream_haiku and forwards text to FishAudio per chunk.
    Returns: { session_id }
    """
    session_id = str(uuid.uuid4())
    text_q = queue.Queue()
    audio_q = queue.Queue()

    def orchestrator():
        try:
            # For each text chunk from stream_haiku, put to text_q and synthesize audio for that chunk
            for chunk in stream_haiku(conversation_id):
                if chunk is None:
                    continue
                text_q.put(chunk)
                # Synthesize audio for this chunk and push bytes to audio_q
                try:
                    for achunk in synthesize_stream(chunk):
                        if isinstance(achunk, (bytes, bytearray, memoryview)):
                            audio_q.put(bytes(achunk))
                        else:
                            audio_q.put(str(achunk).encode('utf-8'))
                except Exception as e:
                    print('synthesize_stream error', e)
                    break
        finally:
            # signal completion
            text_q.put(None)
            audio_q.put(None)

    th = threading.Thread(target=orchestrator, daemon=True)
    SESSIONS[session_id] = {'text_q': text_q, 'audio_q': audio_q, 'thread': th}
    th.start()
    return jsonify({'session_id': session_id})

@app.route('/')
def index():
    # Serve the single-file frontend from the same origin to avoid CORS/file:// issues
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(path):
        return send_file(path)
    return jsonify({"error": "index.html not found"}), 404

@app.route('/record')
def record():
    path = os.path.join(os.path.dirname(__file__), 'record.html')
    if os.path.exists(path):
        return send_file(path)
    return jsonify({"error": "record.html not found"}), 404

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
