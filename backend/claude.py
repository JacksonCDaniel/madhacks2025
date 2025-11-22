import os
from db import get_messages, get_conversation, insert_message

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
    """Stub for calling Claude Haiku. Replace with real API call during integration.
    Expects messages as list of {role, content} dicts in chronological order.
    Returns assistant text.
    """
    # For now, return an echo of the last user message with a prefix.
    last_user = next((m for m in reversed(messages) if m['role'] == 'user'), None)
    if last_user:
        return "Assistant reply (demo): " + last_user.get('content', '')
    return "Hello, I'm DemoAssistant."


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
