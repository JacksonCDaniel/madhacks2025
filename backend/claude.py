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
    system_msg = conv.get('system_message') if conv else None

    # Load all messages (could be optimized)
    messages = get_messages(conversation_id, limit=10000)

    # Identify memory messages (role == 'memory') and recent messages
    memory_messages = [m for m in messages if m['role'] == 'memory']
    regular = [m for m in messages if m['role'] != 'memory']

    # Start accounting tokens with system message
    running = estimate_tokens(system_msg or '')
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
    if system_msg:
        assembled.append({'role': 'system', 'content': system_msg})
    # include memory messages
    for mm in memory_messages:
        assembled.append({'role': 'memory', 'content': mm['content']})
    # include remaining messages
    for m in included:
        assembled.append({'role': m['role'], 'content': m['content']})

    return assembled


def call_haiku(messages):
    """Call Anthropic (Claude) via the `anthropic` package using the hardcoded system prompt.
    Messages must be a chronological list of dicts: {role, content}.
    Returns assistant text.
    """
    client = Anthropic()
    model = 'claude-haiku-4-5-20251001'

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

    # Call the Anthropic Messages API and pass the system prompt as the top-level `system` parameter
    response = client.messages.create(
        max_tokens=1024,
        temperature=0.4,
        messages=msgs,
        model=model,
        system=SYSTEM_PROMPT,
    )

    blocks = []

    for b in response.content:
        if isinstance(b, TextBlock):
            blocks.append(b.text)

    return '\n\n'.join(blocks).strip()


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
