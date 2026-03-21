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

SYSTEM_PROMPT = """You are an Android UI automation expert controlling a phone screen.

You receive:
1. A screenshot with GREEN numbered boxes on clickable elements and RED boxes on non-clickable ones
2. A JSON list of elements matching those box numbers
3. The current goal and action history summary

Your job is to decide the next action.

STRICT RULES:
- ONLY reference elements by their ID number from the JSON list
- NEVER invent element IDs or coordinates
- Keep your thought short — one or two sentences maximum
- If confidence is below 50% on all actions, set needs_help to true
- Always check if your action is helping the current goal

OUTPUT FORMAT — return ONLY valid JSON, nothing else:
{
  "thought": "one sentence about what you see and why",
  "intent_check": "yes or no — is this action helping the goal?",
  "actions": [
    {"type": "TAP", "element_id": 3, "confidence": 0.91},
    {"type": "TAP", "element_id": 5, "confidence": 0.62},
    {"type": "SWIPE", "direction": "up", "confidence": 0.40}
  ],
  "needs_help": false,
  "done": false
}

Action types: TAP(element_id), TYPE(element_id, text), SWIPE(direction: up/down/left/right), DONE
If task is complete set done to true."""


def summarize_history(history):
    if not history:
        return "No actions taken yet."
    if len(history) <= 3:
        return "\n".join(history)
    return "\n".join(history[-3:])


def ask_llm(goal, elements, history, overlay_b64):
    history_summary = summarize_history(history)
    elements_str = json.dumps(elements, indent=2)

    prompt = f"""Goal: {goal}

Progress summary:
{history_summary}

Current screen elements:
{elements_str}

Look at the numbered boxes on the screenshot and decide the next action."""

    last_error = None
    for model in MODELS:
        try:
            messages = [{"role": "user", "content": []}]

            if overlay_b64:
                messages[0]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{overlay_b64}"}
                })

            messages[0]["content"].append({
                "type": "text",
                "text": prompt
            })

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
                    "max_tokens": 400,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                    ] + messages
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
            result['model_used'] = model
            return result

        except json.JSONDecodeError:
            last_error = "LLM returned invalid JSON"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "thought": "All models failed",
        "actions": [],
        "needs_help": True,
        "done": False,
        "model_used": "none",
        "error": last_error
    }
