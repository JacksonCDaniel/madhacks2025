import os
from fishaudio import FishAudio

STREAM_THRESHOLD_CHARS = int(os.environ.get('STREAM_THRESHOLD_CHARS', '3000'))
MODEL_ID = os.environ.get('MODEL_ID', 'e58b0d7efca34eb38d5c4985e378abcb')

client = FishAudio()


def synthesize_bytes(text: str, model_id: str = None) -> bytes:
    """Use FishAudio convert() to get audio bytes."""
    mid = model_id or MODEL_ID
    audio = client.tts.convert(text=text, reference_id=mid)
    # The SDK in the original demo returned bytes-like object
    return audio


def synthesize_stream(text: str, model_id: str = None):
    mid = model_id or MODEL_ID
    for chunk in client.tts.stream(text=text, reference_id=mid):
        yield chunk

