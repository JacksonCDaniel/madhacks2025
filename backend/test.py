# python
import os, requests

BASE = "http://127.0.0.1:5000"
# 1) Create conversation
r = requests.post(f"{BASE}/conversations", json={"user_id":"me","system_message":"Be concise."})
conv = r.json(); conv_id = conv["conversation_id"]

# 2) Send a sync user message and get assistant reply
r = requests.post(f"{BASE}/conversations/{conv_id}/messages",
                  json={"role":"user","content":"What is the weather?","response_mode":"sync"})
assistant = r.json().get("assistant_message")
print("assistant text:", assistant["content"])

# 3) Request TTS for that assistant message (save mp3)
msg_id = assistant["id"]
r = requests.post(f"{BASE}/conversations/{conv_id}/tts",
                  json={"message_id": msg_id, "response_mode":"sync"})
with open("out.mp3", "wb") as f:
    f.write(r.content)

# 4) Create an async job and poll it
r = requests.post(f"{BASE}/conversations/{conv_id}/messages",
                  json={"role":"user","content":"Please write a long report","response_mode":"async"})
job_id = r.json()["job_id"]
import time
for _ in range(20):
    j = requests.get(f"{BASE}/jobs/{job_id}").json()
    print(j)
    print("job:", j.get("status"))
    if j.get("status") in ("done","failed"):
        break
    time.sleep(1)