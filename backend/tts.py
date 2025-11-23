import os
from fishaudio import FishAudio, TTSConfig

# rump
MODEL_ID = os.environ.get('MODEL_ID', 'e58b0d7efca34eb38d5c4985e378abcb')
# dohnny jepp
# MODEL_ID = os.environ.get('TTS_MODEL_ID', 'fb722cecaf534263b409223e524f3e60')
# egirl
# MODEL_ID = os.environ.get('TTS_MODEL_ID', '8ef4a238714b45718ce04243307c57a7')
# bobspo pants
# MODEL_ID = os.environ.get('TTS_MODEL_ID', '54e3a85ac9594ffa83264b8a494b901b')

client = FishAudio()


def synthesize_bytes(text: str, model_id: str = None) -> bytes:
    """Use FishAudio convert() to get audio bytes."""
    mid = model_id or MODEL_ID
    audio = client.tts.convert(text=text, reference_id=mid, latency='balanced')
    # The SDK in the original demo returned bytes-like object
    return audio

def synthesize_stream_gen(text_gen, model_id: str = None):
    mid = model_id or MODEL_ID

    # print(f"[TTS] Starting stream for {len(text)} chars")
    audio_stream = client.tts.stream_websocket(text_gen,
                                     reference_id=mid,
                                     latency='balanced')

    for i, chunk in enumerate(audio_stream):
        # print(f"[TTS] Yielding chunk {i}, size {len(chunk)}")
        yield chunk

    # print("[TTS] Stream complete")


def synthesize_stream(text: str, model_id: str = None):
    mid = model_id or MODEL_ID
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
