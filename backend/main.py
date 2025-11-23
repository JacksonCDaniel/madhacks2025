from dotenv import load_dotenv

load_dotenv()

import os
import uuid
from flask import Flask, request, send_file, jsonify, Response
from flask_socketio import SocketIO
from flask_cors import CORS

# Local modules
from db import init_db, create_conversation, get_conversation, delete_conversation, insert_message, get_messages, now_iso
from claude import build_trimmed_history, stream_haiku, SYSTEM_PROMPT
from tts import synthesize_stream, synthesize_stream_gen
import threading
import queue

# In-memory session store: session_id -> {text_q, audio_q, thread}
SESSIONS = {}

# In-memory message chunk tracker: message_id -> {'chunks': [], 'complete': bool, 'lock': threading.Lock(), 'condition': threading.Condition()}
# This allows multiple readers to wait for chunks as they arrive
MESSAGE_CHUNKS = {}

def get_or_create_message_tracker(message_id):
    """Get or create a message tracker with thread-safe access."""
    if message_id not in MESSAGE_CHUNKS:
        lock = threading.Lock()
        MESSAGE_CHUNKS[message_id] = {
            'chunks': [],
            'complete': False,
            'lock': lock,
            'condition': threading.Condition(lock)
        }
    return MESSAGE_CHUNKS[message_id]

def add_chunk_to_message(message_id, chunk):
    """Add a chunk to a message tracker and notify waiting consumers."""
    tracker = get_or_create_message_tracker(message_id)
    with tracker['condition']:
        tracker['chunks'].append(chunk)
        tracker['condition'].notify_all()

def mark_message_complete(message_id):
    """Mark a message as complete and notify all waiting consumers."""
    if message_id in MESSAGE_CHUNKS:
        tracker = MESSAGE_CHUNKS[message_id]
        with tracker['condition']:
            tracker['complete'] = True
            tracker['condition'].notify_all()

def iter_message_chunks(message_id, start_index=0):
    """Yield chunks from a message as they become available. Blocks until new chunks arrive."""
    tracker = get_or_create_message_tracker(message_id)
    index = start_index

    while True:
        with tracker['condition']:
            # Wait for new chunks or completion
            while index >= len(tracker['chunks']) and not tracker['complete']:
                tracker['condition'].wait(timeout=30.0)  # 30 second timeout
                # Check if still no new data after timeout
                if index >= len(tracker['chunks']) and not tracker['complete']:
                    # Still waiting, continue loop
                    continue

            # Yield any new chunks
            while index < len(tracker['chunks']):
                yield tracker['chunks'][index]
                index += 1

            # If complete and no more chunks, exit
            if tracker['complete'] and index >= len(tracker['chunks']):
                break

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
try:
    ws_secret_key = os.environ['WS_SECRET_KEY']
except KeyError:
    raise RuntimeError("WS_SECRET_KEY environment variable is missing")
app.config['SECRET_KEY'] = ws_secret_key
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "5000"))
TOKEN_BUDGET = int(os.environ.get("TOKEN_BUDGET", "8192"))

# Initialize DB
init_db()

# Helpers
@app.route('/conversations', methods=['POST'])
def create_conversation_endpoint():
    payload = request.get_json()
    user_id = payload.get('user_id')
    problem_title = payload.get('problem_title', '')
    problem_desc = payload.get('problem_desc', '')
    system_message = (SYSTEM_PROMPT
                      .replace("{{problem_title}}", problem_title)
                      .replace("{{problem_desc}}", problem_desc))
    # print(system_message)
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
    conv_id = create_conversation(system_message=system_message, user_id=user_id, metadata=metadata)
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

# def background(sid):
#     socketio.emit('my event', 'WOW', to=sid)
#
#     socketio.sleep(10)
#     socketio.emit('my event', 'WOW', to=sid)

@app.route('/conversations/<conversation_id>/messages', methods=['POST'])
def post_message_endpoint(conversation_id):
    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400
    payload = request.get_json()
    role = payload.get('role', 'user')
    sid = payload.get('sid')
    code = payload.get('code', None)
    content = payload.get('content')
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}

    if not content or not isinstance(content, str) or not content.strip():
        return jsonify({"error": "content is required"}), 400
    if not sid:
        return jsonify({"error": "sid is required"}), 400
    if len(content) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    # persist caller message
    msg_id = insert_message(conversation_id=conversation_id, role=role, content=content, metadata=metadata)

    # For sync responses, call Claude Haiku immediately (trimmed)
    text_gen = stream_haiku(code, conversation_id)

    assistant_id = str(uuid.uuid4())

    get_or_create_message_tracker(assistant_id)

    def gen_chunks():
        chunks = []

        for chunk in text_gen:
            # Emit to WebSocket
            socketio.emit('llm_response', chunk, to=sid)
            # Track chunk in memory for streaming TTS consumers
            add_chunk_to_message(assistant_id, chunk)
            chunks.append(chunk)
            yield chunk

        assistant_text = ''.join(chunks)


        # persist assistant reply
        insert_message(conversation_id=conversation_id, role='assistant', content=assistant_text,
                                      msg_id=assistant_id,
                                      metadata={})

        # Mark this message as complete
        mark_message_complete(assistant_id)

    gen_thing = gen_chunks()

    threading.Thread(target=lambda: list(gen_thing), daemon=True).start()
    return jsonify({"assistant_message_id": assistant_id}), 201
    # try:
    #     tts_response = synthesize_stream_gen(gen_chunks())
    #
    #     resp = Response(tts_response, mimetype='audio/mpeg', direct_passthrough = True)
    #     # Avoid setting Content-Length so Transfer-Encoding: chunked is used
    #     # Advise proxies not to buffer the response
    #     resp.headers['Cache-Control'] = 'no-cache'
    #     resp.headers['X-Accel-Buffering'] = 'no'
    #     resp.headers['Connection'] = 'keep-alive'
    #     resp.headers['X-Message-Id'] = assistant_id
    #     return resp
    # except Exception as e:
    #     mark_message_complete(assistant_id)
    #     return jsonify({"error": "TTS generation failed", "detail": str(e)}), 500

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

@app.route('/conversations/<conversation_id>/messages/<message_id>/tts_stream', methods=['GET'])
def tts_stream_by_message_id(conversation_id, message_id):
    """Stream TTS audio for a message as chunks arrive.
    This works for both in-progress messages (tracked in MESSAGE_CHUNKS)
    and completed messages (from database).

    Query params:
    - start_index: (optional) start from a specific chunk index (default: 0)
    """
    start_index = int(request.args.get('start_index', '0'))

    # Check if this message is being tracked (in-progress or recently completed)
    if message_id in MESSAGE_CHUNKS:
        # Stream from the chunk tracker
        def generate_from_chunks():
            for chunk in iter_message_chunks(message_id, start_index):
                # Synthesize TTS for this chunk and yield audio bytes
                try:
                    for audio_chunk in synthesize_stream(chunk):
                        yield audio_chunk
                except Exception as e:
                    print(f"TTS synthesis error for chunk: {e}")
                    break

        resp = Response(generate_from_chunks(), mimetype='audio/mpeg', direct_passthrough=True)
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        resp.headers['Connection'] = 'keep-alive'
        return resp
    else:
        # Message not being tracked, check if it exists in database
        msgs = get_messages(conversation_id, limit=1000)
        message = next((m for m in msgs if m['id'] == message_id), None)
        if not message:
            return jsonify({"error": "message_id not found"}), 404

        text_to_speak = message['content']
        if len(text_to_speak) > MAX_TEXT_CHARS:
            return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

        # Stream TTS for the complete message
        def generate_complete():
            for chunk in synthesize_stream(text_to_speak):
                yield chunk

        resp = Response(generate_complete(), mimetype='audio/mpeg', direct_passthrough=True)
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        resp.headers['Connection'] = 'keep-alive'
        return resp

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

# @socketio.on('my event')
# def handle_message(data):
#     print('received message: ' + str(data))
#
#     socketio.start_background_task(background, request.sid)

if __name__ == '__main__':
    # cant use reloader with sockets on werkzeug
    socketio.run(app, host='127.0.0.1', port=5000, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
