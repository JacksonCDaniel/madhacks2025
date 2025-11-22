# python
from dotenv import load_dotenv
load_dotenv()

import io
import os
import base64
from flask import Flask, request, send_file, jsonify, render_template_string

app = Flask(__name__)

# Configuration
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "5000"))
# Default model id for TTS (can be overridden via env var)
# boe jiden
# MODEL_ID = os.environ.get('TTS_MODEL_ID', '9b42223616644104a4534968cd612053')
# dohnny jepp
# MODEL_ID = os.environ.get('TTS_MODEL_ID', 'fb722cecaf534263b409223e524f3e60')
# rump himself
MODEL_ID = os.environ.get('TTS_MODEL_ID', 'e58b0d7efca34eb38d5c4985e378abcb')

# Import FishAudio
from fishaudio import FishAudio

# Initialize client (reads from FISH_API_KEY environment variable)
fish_client = FishAudio()

def synthesize_mp3_bytes(text: str) -> bytes:
    # Call the FishAudio TTS
    audio_obj = fish_client.tts.convert(text=text, reference_id=MODEL_ID)

    return audio_obj


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text to Speech & Speech to Text</title>
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
            max-width: 700px;
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
        .small-btn { width:auto; padding:12px 16px; }
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
        .small-muted { color: #666; font-size: 13px; }
        .stt-section { margin-top: 30px; }
        .stt-controls { display:flex; gap:8px; align-items:center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Text to Speech & Speech to Text</h1>
        <p class="subtitle">Enter text and convert to speech, or record/transcribe from your microphone</p>

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

        <div class="stt-section">
            <hr style="margin:28px 0; border: none; height:1px; background:#eee;" />
            <label style="display:block; margin-bottom:8px; color:#333; font-weight:600;">Record from microphone to transcribe</label>

            <div class="stt-controls" style="margin-bottom:10px;">
                <button id="recordBtn" class="small-btn" onclick="toggleRecording()">Start Recording</button>
                <button id="transcribeBtn" class="small-btn" onclick="transcribeRecorded()" disabled>Transcribe Recording</button>
                <span id="recStatus" class="small-muted" style="margin-left:8px;">Not recording</span>
            </div>

            <div id="previewContainer" style="display:none; margin-top:8px;">
                <label style="display:block; color:#333; font-weight:600;">Recording preview</label>
                <audio id="sttPreview" controls></audio>
            </div>

            <div class="loading" id="sttLoading">
                <p>📝 Transcribing audio...</p>
            </div>
            <div class="error" id="sttError"></div>
            <div class="audio-container" id="transcriptContainer">
                <p style="color: #333; margin-bottom:10px;">✅ Transcription</p>
                <div id="transcriptText" style="white-space:pre-wrap; color:#111; background:#fff; padding:12px; border-radius:8px;"></div>
                <div id="transcriptMeta" class="small-muted" style="margin-top:8px;"></div>
                <pre id="segmentsPre" style="margin-top:12px; max-height:200px; overflow:auto; background:#fafafa; padding:10px; border-radius:8px; display:none;"></pre>
            </div>

            <div style="margin-top:16px; color:#666; font-size:13px;">
                Or upload a file:
                <div class="stt-controls" style="margin-top:8px;">
                    <input id="audioFile" type="file" accept="audio/*" />
                    <button id="uploadTranscribeBtn" class="small-btn" onclick="transcribeAudio()">Transcribe Uploaded File</button>
                </div>
            </div>
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

        // STT elements
        const recordBtn = document.getElementById('recordBtn');
        const transcribeBtn = document.getElementById('transcribeBtn');
        const recStatus = document.getElementById('recStatus');
        const sttPreview = document.getElementById('sttPreview');
        const previewContainer = document.getElementById('previewContainer');

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

        // --- STT (file upload) JS ---
        const audioFileInput = document.getElementById('audioFile');
        const uploadTranscribeBtn = document.getElementById('uploadTranscribeBtn');
        const sttLoading = document.getElementById('sttLoading');
        const sttError = document.getElementById('sttError');
        const transcriptContainer = document.getElementById('transcriptContainer');
        const transcriptText = document.getElementById('transcriptText');
        const transcriptMeta = document.getElementById('transcriptMeta');
        const segmentsPre = document.getElementById('segmentsPre');

        async function transcribeAudio() {
            const file = audioFileInput.files[0];
            if (!file) {
                sttShowError('Please select an audio file');
                return;
            }

            // Reset UI
            sttError.classList.remove('show');
            transcriptContainer.classList.remove('show');
            segmentsPre.style.display = 'none';
            transcriptText.textContent = '';
            transcriptMeta.textContent = '';

            sttLoading.classList.add('show');
            uploadTranscribeBtn.disabled = true;

            try {
                const fd = new FormData();
                fd.append('audio', file, file.name);

                const resp = await fetch('/stt', {
                    method: 'POST',
                    body: fd
                });

                if (!resp.ok) {
                    const data = await resp.json().catch(()=>({error:'unknown'}));
                    throw new Error(data.error || 'Transcription failed');
                }

                const data = await resp.json();
                transcriptText.textContent = data.text || '';
                transcriptMeta.textContent = data.duration ? `Duration: ${data.duration}ms` : '';
                if (data.segments && Array.isArray(data.segments) && data.segments.length) {
                    segmentsPre.style.display = 'block';
                    segmentsPre.textContent = JSON.stringify(data.segments, null, 2);
                }
                transcriptContainer.classList.add('show');
            } catch (err) {
                sttShowError(err.message);
            } finally {
                sttLoading.classList.remove('show');
                uploadTranscribeBtn.disabled = false;
            }
        }

        function sttShowError(message) {
            sttError.textContent = '❌ ' + message;
            sttError.classList.add('show');
        }

        // --- Microphone recording and STT ---
        let mediaRecorder = null;
        let recordedChunks = [];

        function updateRecordUI(isRecording) {
            if (isRecording) {
                recordBtn.textContent = 'Stop Recording';
                recStatus.textContent = 'Recording...';
                recordBtn.style.background = '#c0392b';
            } else {
                recordBtn.textContent = 'Start Recording';
                recStatus.textContent = 'Not recording';
                recordBtn.style.background = '';
            }
        }

        async function toggleRecording() {
            // If currently recording, stop
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                updateRecordUI(false);
                return;
            }

            // Start recording
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                sttShowError('Microphone not supported in this browser');
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recordedChunks = [];
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) {
                        recordedChunks.push(e.data);
                    }
                };
                mediaRecorder.onstop = () => {
                    // Create blob and show preview
                    const blob = new Blob(recordedChunks, { type: 'audio/webm' });
                    const url = URL.createObjectURL(blob);
                    sttPreview.src = url;
                    previewContainer.style.display = 'block';
                    transcribeBtn.disabled = false;

                    // Stop all tracks to release microphone
                    stream.getTracks().forEach(t => t.stop());
                };
                mediaRecorder.start();
                updateRecordUI(true);
                transcribeBtn.disabled = true;
            } catch (err) {
                sttShowError('Could not start microphone: ' + err.message);
            }
        }

        async function transcribeRecorded() {
            if (recordedChunks.length === 0) {
                sttShowError('No recording available. Press Start Recording first.');
                return;
            }

            // Prepare UI
            sttError.classList.remove('show');
            transcriptContainer.classList.remove('show');
            segmentsPre.style.display = 'none';
            transcriptText.textContent = '';
            transcriptMeta.textContent = '';

            sttLoading.classList.add('show');
            transcribeBtn.disabled = true;

            try {
                const blob = new Blob(recordedChunks, { type: 'audio/webm' });
                const fd = new FormData();
                // Name the file so server sees a filename and type
                fd.append('audio', blob, 'recording.webm');

                const resp = await fetch('/stt', { method: 'POST', body: fd });

                if (!resp.ok) {
                    const data = await resp.json().catch(() => ({ error: 'unknown' }));
                    throw new Error(data.error || 'Transcription failed');
                }

                const data = await resp.json();
                transcriptText.textContent = data.text || '';
                transcriptMeta.textContent = data.duration ? `Duration: ${data.duration}ms` : '';
                if (data.segments && Array.isArray(data.segments) && data.segments.length) {
                    segmentsPre.style.display = 'block';
                    segmentsPre.textContent = JSON.stringify(data.segments, null, 2);
                }
                transcriptContainer.classList.add('show');
            } catch (err) {
                sttShowError(err.message);
            } finally {
                sttLoading.classList.remove('show');
                transcribeBtn.disabled = false;
            }
        }

        // Cleanup when navigating away (release mic if necessary)
        window.addEventListener('beforeunload', () => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
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


# New STT endpoint
@app.route('/stt', methods=['POST'])
def stt_endpoint():
    """
    Speech-to-text endpoint.
    Accepts multipart/form-data with file field 'audio'.
    Optionally accepts JSON body with base64 audio under 'audio_base64'.
    Returns JSON: { text, duration, segments? }
    """
    audio_bytes = None

    # Prefer uploaded file
    if 'audio' in request.files:
        audio_file = request.files.get('audio')
        audio_bytes = audio_file.read()
    else:
        # Fallback: accept JSON with base64
        if request.is_json:
            payload = request.get_json()
            b64 = payload.get('audio_base64') if isinstance(payload, dict) else None
            if not b64:
                return jsonify({"error": "audio file or audio_base64 is required"}), 400
            try:
                audio_bytes = base64.b64decode(b64)
            except Exception:
                return jsonify({"error": "invalid base64 audio"}), 400
        else:
            return jsonify({"error": "audio file is required"}), 400

    try:
        # Call FishAudio ASR (synchronous)
        result = fish_client.asr.transcribe(audio=audio_bytes)
    except Exception as e:
        return jsonify({"error": "ASR transcription failed", "detail": str(e)}), 500

    resp = {
        "text": getattr(result, "text", "") or "",
        "duration": getattr(result, "duration", None),
    }

    segments = getattr(result, "segments", None)
    if segments:
        try:
            resp["segments"] = [
                {
                    "start": getattr(s, "start", None),
                    "end": getattr(s, "end", None),
                    "text": getattr(s, "text", None)
                } if not isinstance(s, dict) else s
                for s in segments
            ]
        except Exception:
            resp["segments"] = segments

    return jsonify(resp)


if __name__ == '__main__':
    # Run Flask dev server
    app.run(host='127.0.0.1', port=5000, debug=True)
