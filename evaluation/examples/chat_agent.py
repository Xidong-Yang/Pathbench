"""Memory-free agent for a Chat Completions compatible endpoint."""
import json
import os
from urllib.request import Request, urlopen


def respond(messages, tools, memory, seed):
    payload = {"model": os.environ["PATHBENCH_MODEL"], "messages": messages,
               "temperature": 0.0, "seed": seed}
    if tools:
        payload["tools"] = tools
    endpoint = os.environ["PATHBENCH_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + os.environ["PATHBENCH_API_KEY"]}
    request = Request(endpoint, json.dumps(payload).encode(), headers)
    with urlopen(request, timeout=180) as response:
        return json.load(response)["choices"][0]["message"]

