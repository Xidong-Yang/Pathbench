"""Prepend one example from the most recent fully successful intervening task."""
import json

from chat_agent import respond as call_model


def respond(messages, tools, memory, seed):
    if memory:
        # Keep the current system instructions ahead of the demonstration.
        start = next(i for i, message in enumerate(messages) if message["role"] == "user")
        messages = messages[:start] + memory["example"] + messages[start:]
    return call_model(messages, tools, memory, seed)


def learn(memory, episode, seed):
    if episode["score"] < 1:
        return memory
    turn = episode["transcript"][0]
    request = next(m["content"] for m in reversed(turn["messages"]) if m["role"] == "user")
    reply = turn["response"]
    # Show earlier tool choices as text so the simulator executes only current calls.
    calls = reply.get("tool_calls")
    if calls:
        text = json.dumps([call["function"] for call in calls], ensure_ascii=False)
    else:
        text = reply.get("content") or ""
    return {"example": [
        {"role": "user", "content": request[:1200]},
        {"role": "assistant", "content": text[:1200]},
    ]}
