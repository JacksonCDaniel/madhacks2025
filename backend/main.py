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

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"