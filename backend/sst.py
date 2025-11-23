import os
import tempfile
from typing import Dict, Any
from flask import Blueprint, request, jsonify, current_app
from fishaudio import FishAudio

# Create FishAudio client (same pattern as tts.py)
client = FishAudio()

# Maximum allowed upload size in bytes (default 50 MB). Can be overridden via env var.
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_SST_UPLOAD_BYTES", 50 * 1024 * 1024))

# Flask blueprint to expose a simple HTTP API
sst_bp = Blueprint("sst", __name__)


def transcribe_bytes(audio_bytes: bytes) -> Dict[str, Any]:
    """Transcribe raw audio bytes using FishAudio ASR and return a simple dict.

    Returns a dict with keys: text (str) and duration_ms (int|None)
    """
    # The FishAudio demo uses client.asr.transcribe(audio=f.read())
    result = client.asr.transcribe(audio=audio_bytes, language='en')

    print(str(result))
    # Some SDKs return `duration` in ms, adapt gracefully if available
    duration = getattr(result, "duration", None)
    text = getattr(result, "text", None)

    return {"text": text or "", "duration_ms": duration}


def transcribe_file(path: str) -> Dict[str, Any]:
    """Read a file from disk and transcribe it."""
    print(path)
    with open(path, "rb") as f:
        return transcribe_bytes(f.read())


def save_request_to_tempfile(req) -> str:
    """Save request body (multipart file or raw stream) to a temporary file and return its path.

    Enforces MAX_UPLOAD_BYTES to avoid unbounded uploads.
    """
    # Prefer multipart/form-data file upload field named 'file', fall back to any file in request.files
    file_obj = None
    if req.files:
        # If a key named 'file' exists, use it, otherwise pick the first file
        file_obj = req.files.get("file") or next(iter(req.files.values()))

    # Create a temporary file on disk
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    tmp_path = tmp.name
    total = 0

    try:
        if file_obj:
            # Save uploaded file (FileStorage) to temp in chunks
            file_stream = file_obj.stream
            while True:
                chunk = file_stream.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError("upload too large")
                tmp.write(chunk)
        else:
            # Raw streamed body: use request.stream / wsgi.input
            # Flask provides request.environ['wsgi.input'] as the raw input stream
            raw = req.environ.get("wsgi.input") or req.stream
            while True:
                chunk = raw.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError("upload too large")
                tmp.write(chunk)
    finally:
        tmp.flush()
        tmp.close()

    return tmp_path


@sst_bp.route("/sst", methods=["POST"])  # Speech-to-text endpoint
def sst_endpoint():
    """Endpoint accepts an MP3 (multipart 'file' or raw body) and returns JSON {text, duration_ms}.

    Usage examples:
    - multipart/form-data: form field name 'file'
    - raw POST body: POST /sst with content-type audio/mpeg or application/octet-stream
    """
    try:
        tmp_path = save_request_to_tempfile(request)
    except ValueError:
        return jsonify({"error": "upload too large"}), 413
    except Exception as e:
        current_app.logger.exception("Failed to save upload for STT")
        return jsonify({"error": "failed to read upload", "detail": str(e)}), 400

    mp3_path = None
    try:
        # Require ffmpeg to be available and successfully convert the upload
        try:
            import subprocess
            mp3_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            mp3_path = mp3_tmp.name
            mp3_tmp.close()
            # Convert to mp3. If ffmpeg missing or conversion fails, raise.
            subprocess.run([
                "ffmpeg", "-y", "-i", tmp_path, "-vn", "-acodec", "libmp3lame", mp3_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError as e:
            current_app.logger.exception("ffmpeg not found")
            return jsonify({"error": "ffmpeg_not_found", "detail": "ffmpeg is required for SST and was not found on the server."}), 500
        except Exception as e:
            current_app.logger.exception("ffmpeg conversion failed")
            return jsonify({"error": "ffmpeg_conversion_failed", "detail": str(e)}), 500

        # If conversion succeeded, transcribe the produced MP3 file
        result = transcribe_file(mp3_path)
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("STT transcription failed")
        return jsonify({"error": "stt_failed", "detail": str(e)}), 500
    finally:
        # Cleanup tempfile(s)
        try:
            if mp3_path:
                pass
                # os.unlink(mp3_path)
        except Exception:
            pass
        try:
            pass
            # os.unlink(tmp_path)
        except Exception:
            pass


# Convenience function for non-HTTP usage
def transcribe_stream_generator(stream_gen) -> Dict[str, Any]:
    """Accept an iterator/generator yielding bytes-like chunks, write to temp file and transcribe."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_path = tmp.name
    total = 0
    try:
        for chunk in stream_gen:
            if not chunk:
                continue
            tmp.write(chunk)
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise ValueError("stream too large")
        tmp.flush()
        tmp.close()
        return transcribe_file(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# If the user imports this module, they can either register the blueprint on their Flask app:
#   from sst import sst_bp
#   app.register_blueprint(sst_bp, url_prefix='/api')
# Or call transcribe_bytes/transcribe_file/transcribe_stream_generator directly.
