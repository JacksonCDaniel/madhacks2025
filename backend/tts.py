import os
from fishaudio import FishAudio, TTSConfig
from typing import Optional

# rump
# MODEL_ID = os.environ.get('MODEL_ID', 'e58b0d7efca34eb38d5c4985e378abcb')
# dohnny jepp
# MODEL_ID = os.environ.get('TTS_MODEL_ID', 'fb722cecaf534263b409223e524f3e60')
# egirl
# MODEL_ID = os.environ.get('TTS_MODEL_ID', '8ef4a238714b45718ce04243307c57a7')
# bobspo pants
# MODEL_ID = os.environ.get('TTS_MODEL_ID', '54e3a85ac9594ffa83264b8a494b901b')
# male
MALE_MODEL_ID = os.environ.get('M_MODEL_ID', '802e3bc2b27e49c2995d23ef70e6ac89')
# female
FEMALE_MODEL_ID = os.environ.get('F_MODEL_ID', 'b545c585f631496c914815291da4e893')
# default
DEFAULT_MODEL_ID = os.environ.get('D_MODEL_ID', FEMALE_MODEL_ID)

NAME_TO_MODEL = {
    'alice': FEMALE_MODEL_ID,
    'bob': MALE_MODEL_ID,
}

client = FishAudio()

def choose_model_id(model_id: Optional[str] = None) -> str:
    """
    Resolve a model id from:
      - a frontend voice name (e.g. 'Alice' -> FEMALE_MODEL_ID),
      - frontend placeholders: 'MALE_MODEL_ID' / 'FEMALE_MODEL_ID',
      - simple labels 'male' / 'female',
      - or a literal reference id (returned as-is).
    Falls back to DEFAULT_MODEL_ID.
    """
    if not model_id:
        return DEFAULT_MODEL_ID

    low = model_id.strip().lower()

    # frontend voice names
    if low in NAME_TO_MODEL:
        return NAME_TO_MODEL[low]

    # placeholders and simple labels
    if model_id == "MALE_MODEL_ID" or low == "male":
        return MALE_MODEL_ID
    if model_id == "FEMALE_MODEL_ID" or low == "female":
        return FEMALE_MODEL_ID

    # otherwise assume it's already a real reference id
    return model_id

def synthesize_bytes(text: str, model_id: str = None) -> bytes:
    """Use FishAudio convert() to get audio bytes."""
    mid = choose_model_id(model_id)
    audio = client.tts.convert(text=text, reference_id=mid, latency='balanced')
    # The SDK in the original demo returned bytes-like object
    return audio

def synthesize_stream_gen(text_gen, model_id: str = None):
    mid = choose_model_id(model_id)

    # print(f"[TTS] Starting stream for {len(text)} chars")
    audio_stream = client.tts.stream_websocket(text_gen,
                                     reference_id=mid,
                                     latency='balanced')

    for i, chunk in enumerate(audio_stream):
        # print(f"[TTS] Yielding chunk {i}, size {len(chunk)}")
        yield chunk

    # print("[TTS] Stream complete")


def synthesize_stream(text: str, model_id: str = None):
    mid = choose_model_id(model_id)
    def text_chunks():
        # print(text)
        yield text

    # print(f"[TTS] Starting stream for {len(text)} chars")
    audio_stream = client.tts.stream_websocket(text_chunks(),
                                     reference_id=mid,
                                     latency='balanced')

    for i, chunk in enumerate(audio_stream):
        # print(f"[TTS] Yielding chunk {i}, size {len(chunk)}")
        yield chunk

    # print("[TTS] Stream complete")
