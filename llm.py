import os
import json
import requests

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "meta-llama/llama-3.2-11b-vision-instruct",
    "google/gemini-2.0-flash-001",
    "google/gemini-2.5-flash",
]

SYSTEM_PROMPT = """You are an Android phone controller.
You are given a task and a list of text elements visible on the screen with their coordinates.
Your job is to decide the next single action to take.

Each element looks like: {"text": "Suphal", "x": 400, "y": 650}
The x and y are the exact center coordinates of that text on screen.

RULES:
- Only ONE action at a time
- Use the exact x and y from the elements list — never guess coordinates
- If the target element is in the list, tap it
- If not found, swipe up to reveal more content
- If task is complete, say done
- Always explain your reasoning

Reply ONLY with valid JSON, nothing else:
{
  "action": "tap" | "type" | "swipe_up" | "swipe_down" | "wait" | "done" | "error",
  "x": 123,
  "y": 456,
  "text": "only if action is type",
  "reason": "what you see and why"
}"""


def ask_llm(task, elements, context):
    elements_str = json.dumps(elements, indent=2)
    prompt = f"TASK: {task}\n\nCONTEXT: {context}\n\nELEMENTS ON SCREEN:\n{elements_str}\n\nWhat is the next action?"

    last_error = None
    for model in MODELS:
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://flowscript.app",
                    "X-Title": "FlowScript"
                },
                json={
                    "model": model,
                    "max_tokens": 300,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=30
            )

            data = response.json()

            if response.status_code == 429:
                raise Exception("rate_limited")

            if "error" in data:
                raise Exception(data["error"].get("message", "unknown error"))

            raw = data['choices'][0]['message']['content'].strip()

            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start != -1 and end != 0:
                raw = raw[start:end]

            result = json.loads(raw)
            result.setdefault('action', 'error')
            result.setdefault('x', 0)
            result.setdefault('y', 0)
            result.setdefault('text', '')
            result.setdefault('reason', '')
            result['model_used'] = model
            return result

        except Exception as e:
            last_error = str(e)
            continue

    return {
        "action": "error",
        "x": 0, "y": 0, "text": "",
        "reason": f"All models failed. Last error: {last_error}",
        "model_used": "none"
    }
  
