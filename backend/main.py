# from fishaudio import FishAudio
# from fishaudio.utils import play, save
#
# # Initialize client (reads from FISH_API_KEY environment variable)
# client = FishAudio()
#
# # Generate and play audio
# audio = client.tts.convert(text="Hello, playing from Fish Audio!")
# play(audio)
#
# # Generate and save audio
# audio = client.tts.convert(text="Saving this audio to a file!")
# save(audio, "output.mp3")

from dotenv import load_dotenv
load_dotenv()

import io
import os
import time
import threading
from flask import Flask, request, send_file, jsonify, render_template_string

app = Flask(__name__)

# Configuration
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "5000"))
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))

# Import FishAudio
from fishaudio import FishAudio

# Initialize client (reads from FISH_API_KEY environment variable)
fish_client = FishAudio()

# Simple in-memory per-IP rate limiter
_rate_lock = threading.Lock()
_rate_store = {}  # ip -> [timestamps]

def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    window_start = now - 60
    with _rate_lock:
        q = _rate_store.setdefault(ip, [])
        # drop old
        while q and q[0] < window_start:
            q.pop(0)
        if len(q) >= RATE_LIMIT_PER_MIN:
            return False
        q.append(now)
        return True


def synthesize_mp3_bytes(text: str) -> bytes:
    """Synthesize MP3 bytes using FishAudio."""
    audio_obj = fish_client.tts.convert(text=text)

    # audio_obj may be raw bytes, or have attributes
    if isinstance(audio_obj, (bytes, bytearray)):
        return bytes(audio_obj)

    # Check common attribute names
    for attr in ("content", "audio", "data"):
        if hasattr(audio_obj, attr):
            val = getattr(audio_obj, attr)
            if isinstance(val, (bytes, bytearray)):
                return bytes(val)

    # If it has a save helper, write to temp file and read back
    if hasattr(audio_obj, "save"):
        tmp = "temp_out.mp3"
        audio_obj.save(tmp)
        with open(tmp, "rb") as f:
            data = f.read()
        try:
            os.remove(tmp)
        except Exception:
            pass
        return data

    # If it has a write helper, write to buffer
    if hasattr(audio_obj, "write"):
        buf = io.BytesIO()
        audio_obj.write(buf)
        buf.seek(0)
        return buf.read()

    raise RuntimeError(f"Unable to extract bytes from FishAudio response: {type(audio_obj)}")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text to Speech</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }
        textarea {
            width: 100%;
            min-height: 150px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .char-count {
            text-align: right;
            color: #999;
            font-size: 12px;
            margin-top: 5px;
            margin-bottom: 20px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .audio-container {
            margin-top: 30px;
            padding: 20px;
            background: #f5f5f5;
            border-radius: 10px;
            display: none;
        }
        .audio-container.show {
            display: block;
        }
        audio {
            width: 100%;
            margin-top: 10px;
        }
        .error {
            margin-top: 20px;
            padding: 15px;
            background: #fee;
            border: 1px solid #fcc;
            border-radius: 10px;
            color: #c33;
            display: none;
        }
        .error.show {
            display: block;
        }
        .loading {
            text-align: center;
            color: #667eea;
            margin-top: 20px;
            display: none;
        }
        .loading.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Text to Speech</h1>
        <p class="subtitle">Enter your text and convert it to speech</p>
        
        <textarea id="textInput" placeholder="Type or paste your text here..." maxlength="5000"></textarea>
        <div class="char-count">
            <span id="charCount">0</span> / 5000 characters
        </div>
        
        <button id="submitBtn" onclick="generateSpeech()">Generate Speech</button>
        
        <div class="loading" id="loading">
            <p>🔊 Generating audio...</p>
        </div>
        
        <div class="error" id="error"></div>
        
        <div class="audio-container" id="audioContainer">
            <p style="color: #333; margin-bottom: 10px;">✅ Audio generated successfully!</p>
            <audio id="audioPlayer" controls></audio>
        </div>
    </div>

    <script>
        const textInput = document.getElementById('textInput');
        const charCount = document.getElementById('charCount');
        const submitBtn = document.getElementById('submitBtn');
        const loading = document.getElementById('loading');
        const error = document.getElementById('error');
        const audioContainer = document.getElementById('audioContainer');
        const audioPlayer = document.getElementById('audioPlayer');

        // Update character count
        textInput.addEventListener('input', function() {
            charCount.textContent = this.value.length;
        });

        async function generateSpeech() {
            const text = textInput.value.trim();
            
            // Validation
            if (!text) {
                showError('Please enter some text');
                return;
            }
            
            // Hide previous results
            error.classList.remove('show');
            audioContainer.classList.remove('show');
            
            // Show loading
            loading.classList.add('show');
            submitBtn.disabled = true;
            
            try {
                const response = await fetch('/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text: text })
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to generate speech');
                }
                
                // Get audio blob
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                
                // Set audio source and show player
                audioPlayer.src = audioUrl;
                audioContainer.classList.add('show');
                
                // Auto-play the audio
                audioPlayer.play().catch(err => {
                    console.log('Auto-play prevented:', err);
                });
                
            } catch (err) {
                showError(err.message);
            } finally {
                loading.classList.remove('show');
                submitBtn.disabled = false;
            }
        }

        function showError(message) {
            error.textContent = '❌ ' + message;
            error.classList.add('show');
        }

        // Allow Enter key to submit (with Shift+Enter for new line)
        textInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                generateSpeech();
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    """Serve the interactive HTML page."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/tts', methods=['POST'])
def tts_endpoint():
    """API endpoint to generate speech from text."""
    # Rate limit per IP
    ip = request.remote_addr or request.environ.get('REMOTE_ADDR', 'unknown')
    if not _check_rate_limit(ip):
        return jsonify({"error": "rate limit exceeded"}), 429

    if not request.is_json:
        return jsonify({"error": "expected JSON body"}), 400

    payload = request.get_json()
    text = payload.get('text') if isinstance(payload, dict) else None

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text is required"}), 400

    if len(text) > MAX_TEXT_CHARS:
        return jsonify({"error": f"text too long (max {MAX_TEXT_CHARS} chars)"}), 413

    try:
        audio_bytes = synthesize_mp3_bytes(text)
    except Exception as e:
        return jsonify({"error": "TTS generation failed", "detail": str(e)}), 500

    buf = io.BytesIO(audio_bytes)
    buf.seek(0)
    # Return as inline audio (not attachment) so it plays in the browser
    return send_file(buf, mimetype='audio/mpeg', as_attachment=False)


if __name__ == '__main__':
    # Run Flask dev server
    app.run(host='127.0.0.1', port=5000, debug=True)
