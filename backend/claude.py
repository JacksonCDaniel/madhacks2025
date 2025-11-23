import os
from db import get_messages, get_conversation, insert_message
from anthropic import Anthropic
from anthropic.types import TextBlock

# Hardcoded system prompt (interviewer persona). Must be concise by design; model should follow rules.
SYSTEM_PROMPT =  """
You are an interviewer at Google for a technical software engineering new grad role.
Simulate a realistic LeetCode-style interview.

INTERVIEW FLOW RULES:
1. Present one coding problem.
2. Discuss a test case and think through it together.
3. Ask them to give a high-level plan before coding.
4. Once they provide a plan, tell them to implement it.
5. After they code, walk through a test case.
6. Ask 1–2 follow-up or optimization questions.

BEHAVIOR RULES:
- Keep responses concise. (Strict requirement)
- Never write code for the interviewee.
- Ask clarifying questions when needed.
- Give feedback without giving the solution.
- Encourage structure and communication.
- Do NOT mention common named solutions (e.g., “two pointers”, “sliding window”).
- Only guide; do not tutor.
- If the candidate is wrong, nudge them to reason deeper.
- Never solve the problem for them.
- Your response will be spoken aloud. NO FORMATTING. NO WEIRD CHARACTERS.


CREDIT-SAVING RULE:
- Your responses MUST be concise and under 200 words.
- Do not expand unnecessarily.
- Do not restate large sections of the problem unless required.

Your goal:
Simulate the interviewer as realistically and concisely as possible.

DO NOT USE MARKDOWN FORMATTING. USE SIMPLE ENGLISH LANGUAGE TEXT.
"""

TOKEN_BUDGET = int(os.environ.get('TOKEN_BUDGET', '8192'))


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def build_trimmed_history(conversation_id: str, token_budget: int = None):
    """Return a list of messages (dicts) trimmed to fit within token_budget.
    Order: chronological (oldest->newest), starting with system message then memory and recent messages.
    """
    token_budget = token_budget or TOKEN_BUDGET
    conv = get_conversation(conversation_id)

    # Load all messages (could be optimized)
    messages = get_messages(conversation_id, limit=10000)

    # Identify memory messages (role == 'memory') and recent messages
    memory_messages = [m for m in messages if m['role'] == 'memory']
    regular = [m for m in messages if m['role'] != 'memory']

    # Start accounting tokens with system message
    running = 0
    included = []

    # Iterate recent messages in reverse chronological order
    for m in reversed(regular):
        t = m.get('tokens_est') or estimate_tokens(m.get('content', ''))
        if running + t <= token_budget and len(included) < 200:
            included.append(m)
            running += t
        else:
            # stop including older messages
            break

    # included currently is newest-first; reverse to chronological
    included = list(reversed(included))

    assembled = []
    # include memory messages
    for mm in memory_messages:
        assembled.append({'role': 'memory', 'content': mm['content']})
    # include remaining messages
    for m in included:
        assembled.append({'role': m['role'], 'content': m['content']})

    return assembled

client = Anthropic()
model = 'claude-haiku-4-5-20251001'
# Use temperature 0.0 for deterministic responses
temperature = 0.0

def call_haiku(messages):
    """Call Anthropic (Claude) via the `anthropic` package using the hardcoded system prompt.
    Messages must be a chronological list of dicts: {role, content}.
    Returns assistant text.
    """

    msgs = build_msg_ctx(messages)

    # Call the Anthropic Messages API and pass the system prompt as the top-level `system` parameter
    response = client.messages.create(
        max_tokens=1024,
        temperature=temperature,
        messages=msgs,
        model=model,
        system=SYSTEM_PROMPT,
    )

    blocks = []

    for b in response.content:
        if isinstance(b, TextBlock):
            blocks.append(b.text)

    return '\n\n'.join(blocks).strip()


def build_msg_ctx(messages):
    # Build structured messages array for the Messages API (only user/assistant roles)
    msgs = []
    for m in messages:
        role = m.get('role')
        content = m.get('content', '')
        # map memory -> user (keep content as a short fact)
        if role == 'memory':
            msgs.append({"role": "user", "content": "Memory: " + content})
        elif role == 'user':
            msgs.append({"role": "user", "content": content})
        elif role == 'assistant':
            msgs.append({"role": "assistant", "content": content})
    return msgs


def build_summary(messages_chunk):
    # Simple heuristic summary: concatenate first sentences up to limit
    texts = [m['content'] for m in messages_chunk]
    combined = '\n'.join(texts)
    # naive: take first 500 chars
    summary = combined[:500]
    return summary


# helper to create a memory message after summarization
def insert_summary_message(conversation_id, summary_text):
    return insert_message(conversation_id=conversation_id, role='memory', content=summary_text, metadata={})

def stream_haiku(conversation_id):
    # Build trimmed history synchronously
    messages = build_trimmed_history(conversation_id)

    msgs = build_msg_ctx(messages)

    # print(msgs)

    # Call the Anthropic Messages API and pass the system prompt as the top-level `system` parameter
    with client.messages.stream(
        max_tokens=1024,
        temperature=temperature,
        messages=msgs,
        model=model,
        system=SYSTEM_PROMPT,
    ) as stream:
        for text in stream.text_stream:
            # print(text)
            yield text

def build_static_code_review_msgs(conversation_id: str, files: dict, language: str = 'python', extra_instructions: str = None):
    """
    Build messages for a static-only code review. This explicitly tells the LLM
    that it must not suggest running the code or assume test results; instead
    it should analyze the provided source files statically, point out likely
    bugs, edge cases, performance concerns, and ask clarifying questions.

    - `files` is a dict filename -> source text
    - `language` is a short string like 'python' or 'java'
    """
    history = build_trimmed_history(conversation_id)

    system_text = SYSTEM_PROMPT + (
        "\n\nSTATIC CODE REVIEW MODE:\nYou must NOT assume code has been executed, and do NOT instruct the user to run or execute code.\n"
        "Analyze the submitted files statically: find likely logic errors, edge cases, API misuse, security issues, style problems, missing tests, and ask concise clarifying questions you need to give better feedback.\n"
        "DO NOT propose runnable patches or full solutions. Provide short code snippets only when illustrating a single-line fix; keep overall feedback concise (<200 words)."
    )

    msgs = []
    for m in history:
        msgs.append({'role': m['role'], 'content': m['content']})

    parts = [f"Please perform a static code review for the candidate's submission in {language}. Do not run or assume any execution results."]

    for fname, src in (files or {}).items():
        safe_src = (src or '')
        parts.append(f"FILE: {fname}\n" + safe_src[:8000])

    if extra_instructions:
        parts.append(str(extra_instructions))

    user_content = "\n\n".join(parts)
    msgs.append({'role': 'user', 'content': user_content})
    return system_text, msgs


def stream_static_code_review(conversation_id: str, files: dict, language: str = 'python', extra_instructions: str = None):
    """
    Stream static-only critique from the model; yields partial text chunks.
    """
    system_text, msgs = build_static_code_review_msgs(conversation_id, files, language, extra_instructions)
    msgs_for_api = build_msg_ctx(msgs)

    with client.messages.stream(
        max_tokens=1024,
        temperature=0.2,
        messages=msgs_for_api,
        model=model,
        system=system_text,
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk
