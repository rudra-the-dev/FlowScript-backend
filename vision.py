import json
import time
from flask import Blueprint, request, jsonify
from ocr import extract_text_elements
from llm import ask_llm
from overlay import draw_overlay

vision_bp = Blueprint('vision', __name__)

MAX_STEPS = 15


def normalize_element(el, eid):
    x = el.get('x', 0)
    y = el.get('y', 0)
    bounds = el.get('bounds', [x - 40, y - 20, x + 40, y + 20])
    return {
        "id": eid,
        "text": el.get('text', '') or el.get('content_desc', '') or '',
        "clickable": bool(el.get('clickable', False)),
        "bounds": bounds,
        "x": (bounds[0] + bounds[2]) // 2,
        "y": (bounds[1] + bounds[3]) // 2,
    }


def assign_ids(elements):
    return [normalize_element(el, i + 1) for i, el in enumerate(elements)]


def validate_action(action, elements):
    action_type = action.get('type')

    if action_type in ['SWIPE', 'DONE']:
        return True, None

    element_id = action.get('element_id')
    if element_id is None:
        return False, "No element_id provided"

    element = next((e for e in elements if e.get('id') == element_id), None)
    if not element:
        return False, f"Element ID {element_id} not found on screen"

    if action_type == 'TAP' and not element.get('clickable', False):
        return False, f"Element {element_id} ('{element.get('text')}') is not clickable"

    return True, None


def get_expected_outcome(action, element):
    action_type = action.get('type')
    text = (element.get('text', '') if element else '').lower()

    if action_type == 'TAP':
        if any(w in text for w in ['search', 'find', 'look']):
            return "keyboard should be visible"
        if any(w in text for w in ['send', 'post', 'submit']):
            return "message should be sent"
        return "new screen or state should appear"
    if action_type == 'TYPE':
        return "text should appear in the input field"
    if action_type == 'SWIPE':
        return "screen content should scroll"
    return "screen should change"


def verify_progress(prev_elements, curr_elements, expected):
    prev_texts = set(e.get('text', '') for e in prev_elements)
    curr_texts = set(e.get('text', '') for e in curr_elements)
    changed = prev_texts != curr_texts
    return {
        "changed": changed,
        "expected": expected,
        "verdict": "likely succeeded" if changed else "screen unchanged — may have failed"
    }


@vision_bp.route('/vision/next-action', methods=['POST'])
def next_action():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON body"}), 400

    screenshot_b64 = data.get('screenshot')
    task = data.get('task', '')
    history = data.get('history', [])
    accessibility_tree = data.get('accessibility_tree', [])
    failure_counts = data.get('failure_counts', {})
    prev_elements = data.get('prev_elements', [])
    step = data.get('step', 0)
    prev_expected = data.get('prev_expected', None)

    if not screenshot_b64:
        return jsonify({"error": "No screenshot provided"}), 400
    if not task:
        return jsonify({"error": "No task provided"}), 400

    # Global step limit
    if step >= MAX_STEPS:
        return jsonify({
            "status": "failed",
            "thought": f"Task did not complete within {MAX_STEPS} steps"
        })

    # Step 1 — build normalized element list
    if accessibility_tree:
        elements = assign_ids(accessibility_tree)
    else:
        try:
            elements = assign_ids(extract_text_elements(screenshot_b64))
        except Exception as e:
            elements = []
            print(f"OCR failed: {e}")

    # Step 2 — verify previous action outcome
    verification = None
    if prev_elements and prev_expected:
        verification = verify_progress(prev_elements, elements, prev_expected)
        print(f"Verification: {verification['verdict']}")

    # Step 3 — draw overlay
    try:
        overlay_b64 = draw_overlay(screenshot_b64, elements)
    except Exception as e:
        overlay_b64 = screenshot_b64
        print(f"Overlay failed: {e}")

    # Step 4 — ask LLM
    llm_result = ask_llm(task, elements, history, overlay_b64)

    if llm_result.get('done'):
        return jsonify({
            "status": "done",
            "thought": llm_result.get('thought'),
            "model_used": llm_result.get('model_used')
        })

    if llm_result.get('needs_help') or not llm_result.get('actions'):
        return jsonify({
            "status": "needs_help",
            "thought": llm_result.get('thought', 'Not sure what to do next'),
            "model_used": llm_result.get('model_used')
        })

    # Step 5 — enforce intent check
    if llm_result.get('intent_check', 'yes').lower() == 'no':
        return jsonify({
            "status": "needs_help",
            "thought": f"Action not aligned with goal: {llm_result.get('thought')}",
            "model_used": llm_result.get('model_used')
        })

    # Step 6 — try actions in order with validation
    actions = llm_result.get('actions', [])
    for action in actions:
        valid, reason = validate_action(action, elements)
        if not valid:
            action_key = f"{action.get('type')}_{action.get('element_id')}"
            failure_counts[action_key] = failure_counts.get(action_key, 0) + 1

            if failure_counts[action_key] >= 3:
                return jsonify({
                    "status": "needs_help",
                    "thought": f"Failed {failure_counts[action_key]} times: {reason}",
                    "model_used": llm_result.get('model_used')
                })
            continue

        element = next((e for e in elements if e.get('id') == action.get('element_id')), None)
        expected_outcome = get_expected_outcome(action, element)

        response = {
            "status": "action",
            "thought": llm_result.get('thought'),
            "intent_check": llm_result.get('intent_check'),
            "action": action.get('type'),
            "element_id": action.get('element_id'),
            "confidence": action.get('confidence', 0),
            "model_used": llm_result.get('model_used'),
            "failure_counts": failure_counts,
            "prev_elements": elements,
            "prev_expected": expected_outcome,
            "step": step + 1,
            "verification": verification,
            "time_delay": 600
        }

        if element:
            response['x'] = element.get('x', 0)
            response['y'] = element.get('y', 0)
            response['element_text'] = element.get('text', '')

        if action.get('type') == 'TYPE':
            response['text'] = action.get('text', '')

        if action.get('type') == 'SWIPE':
            response['direction'] = action.get('direction', 'up')

        return jsonify(response)

    return jsonify({
        "status": "needs_help",
        "thought": "All proposed actions were invalid",
        "model_used": llm_result.get('model_used')
    })


@vision_bp.route('/vision/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "service": "FlowScript Vision v2",
        "pipeline": ["accessibility", "ocr", "overlay", "react_llm", "intent_check", "validation", "verification"]
    })
