import json
from flask import Blueprint, request, jsonify
from ocr import extract_text_elements
from llm import ask_llm

vision_bp = Blueprint('vision', __name__)


@vision_bp.route('/vision/next-action', methods=['POST'])
def next_action():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON body"}), 400

    screenshot_b64 = data.get('screenshot')
    task = data.get('task', '')
    context = data.get('context', 'No previous actions taken.')
    accessibility_tree = data.get('accessibility_tree', None)

    if not screenshot_b64:
        return jsonify({"error": "No screenshot provided"}), 400
    if not task:
        return jsonify({"error": "No task provided"}), 400

    # Step 1 — Try accessibility tree first if provided
    if accessibility_tree:
        result = search_accessibility_tree(accessibility_tree, task)
        if result:
            result['source'] = 'accessibility'
            return jsonify(result)

    # Step 2 — OCR extracts all text and coordinates from screenshot
    try:
        elements = extract_text_elements(screenshot_b64)
    except Exception as e:
        elements = []
        print(f"OCR failed: {e}")

    # Step 3 — LLM reasons about extracted elements
    result = ask_llm(task, elements, context)
    result['source'] = 'ocr+llm'
    result['elements_found'] = len(elements)

    return jsonify(result)


def search_accessibility_tree(tree, task):
    """
    Search accessibility tree for elements matching the task.
    Tree is a list of nodes: [{"text": "Suphal", "x": 400, "y": 650, "clickable": true}]
    """
    if not tree:
        return None

    task_lower = task.lower()
    words = task_lower.split()

    for node in tree:
        node_text = node.get('text', '').lower()
        if not node_text:
            continue
        if any(word in node_text for word in words if len(word) > 2):
            if node.get('clickable', False):
                return {
                    "action": "tap",
                    "x": node.get('x', 0),
                    "y": node.get('y', 0),
                    "text": "",
                    "reason": f"Found '{node.get('text')}' in accessibility tree"
                }

    return None


@vision_bp.route('/vision/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "service": "FlowScript Vision",
        "pipeline": ["accessibility_tree", "ocr", "llm"],
        "models": ["llama-3.2-11b-vision", "gemini-2.0-flash", "gemini-2.5-flash"]
    })
  
