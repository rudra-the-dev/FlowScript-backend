import base64
import io
import numpy as np
from PIL import Image
import easyocr

reader = None

def get_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False)
    return reader

def extract_text_elements(screenshot_b64):
    img_bytes = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    img_np = np.array(img)

    results = get_reader().readtext(img_np)

    elements = []
    for (bbox, text, confidence) in results:
        if confidence < 0.4:
            continue
        top_left = bbox[0]
        bottom_right = bbox[2]
        x = int((top_left[0] + bottom_right[0]) / 2)
        y = int((top_left[1] + bottom_right[1]) / 2)
        elements.append({
            "text": text.strip(),
            "x": x,
            "y": y,
            "confidence": round(confidence, 2)
        })

    return elements
  
