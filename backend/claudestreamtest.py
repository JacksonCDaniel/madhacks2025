from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

client = Anthropic()
model = 'claude-haiku-4-5-20251001'
with client.messages.stream(
        max_tokens=1024,
        temperature=0.0,
        messages=[{"role": "user", "content": "Hi!!!"}],
        model=model,
        system="Say hello to the user!",
) as stream:
    for text in stream.text_stream:
        print(text, end='')