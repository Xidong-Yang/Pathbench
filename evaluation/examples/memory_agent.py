"""Prepend one example from the most recent fully successful intervening task."""
import json

from chat_agent import ChatAgent


class MemoryAgent(ChatAgent):
    def __init__(self, seed):
        super().__init__(seed)
        self.example = []

    def respond(self, messages, tools, context):
        if self.example:
            # Keep the current system instructions ahead of the demonstration.
            start = next(i for i, message in enumerate(messages) if message["role"] == "user")
            messages = messages[:start] + self.example + messages[start:]
        return super().respond(messages, tools, context)

    def observe(self, episode):
        if episode["score"] < 1:
            return
        turn = episode["transcript"][0]
        request = next(m["content"] for m in reversed(turn["messages"]) if m["role"] == "user")
        reply = turn["response"]
        # Show earlier tool choices as text so the simulator executes only current calls.
        calls = reply.get("tool_calls")
        if calls:
            text = json.dumps([call["function"] for call in calls], ensure_ascii=False)
        else:
            text = reply.get("content") or ""
        self.example = [
            {"role": "user", "content": request[:1200]},
            {"role": "assistant", "content": text[:1200]},
        ]


def create_agent(context):
    return MemoryAgent(context["seed"])
