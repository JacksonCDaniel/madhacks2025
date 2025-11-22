import os
from anthropic import Anthropic


# Initialize Claude client
def load_api_key():
    key_path = os.path.join(os.path.dirname(__file__), "config", "anthropic_key.txt")
    try:
        with open(key_path, "r") as f:
            key = f.read().strip()
            if not key:
                raise ValueError("anthropic_key.txt is empty")
            return key
    except FileNotFoundError:
        raise FileNotFoundError(
            f"API key file not found at: {key_path}\n"
            "Create config/anthropic_key.txt and put your Claude API key inside."
        )


client = Anthropic(api_key=load_api_key())
# ------------------------------------
# GOOGLE INTERVIEWER SYSTEM PROMPT
# ------------------------------------
INTERVIEWER_SYSTEM_PROMPT = """
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

CREDIT-SAVING RULE:
- Your responses MUST be concise and under 200 words.
- Do not expand unnecessarily.
- Do not restate large sections of the problem unless required.

Your goal:
Simulate the interviewer as realistically and concisely as possible.
"""

# ------------------------------------
# OPTIONAL TOOLS FOR CLAUDE
# (Example: generate a test case)
# ------------------------------------
TOOLS = [
    {
        "name": "get_test_case",
        "description": "Return a small test case example for the given coding problem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {"type": "string"}
            },
            "required": ["problem"]
        }
    }
]


def get_test_case(problem: str):
    # keep output tiny to avoid credit usage
    return {"test_case": f"Small example for problem: {problem} — keep concise."}


# ------------------------------------
# MAIN LLM FUNCTION
# ------------------------------------
def run_interviewer_agent(user_input: str) -> str:
    """
    Sends the user_input to Claude and returns the interviewer's response.
    Output is strictly limited to avoid overspending credits.
    """

    response = client.messages.create(
        model="claude-4.5-haiku",
        max_tokens=300,  # HARD LIMIT (prevents credit burn)
        temperature=0.4,
        system=INTERVIEWER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_input}
        ],
        tools=TOOLS
    )

    message = response.content[0]

    # CASE 1: Claude wants to use a tool (e.g., generate a test case)
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_outputs = []

        for call in message.tool_calls:
            if call["name"] == "get_test_case":
                args = call["input"]
                result = get_test_case(**args)
                tool_outputs.append({
                    "tool_call_id": call["id"],
                    "output": result
                })

        # Send tool result BACK to Claude so it can finish the message
        followup = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            temperature=0.4,
            system=INTERVIEWER_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=[
                {"role": "user", "content": user_input},
                message,
                {"role": "tool", "content": tool_outputs}
            ]
        )

        return followup.content[0].text

    # CASE 2: Normal response
    return message.text
