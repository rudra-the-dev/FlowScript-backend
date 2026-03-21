import base64
import io
import pytesseract
from PIL import Image

def extract_text_elements(screenshot_b64):
    img_bytes = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    elements = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = int(data['conf'][i])

        if not text or conf < 40:
            continue

        x = data['left'][i] + data['width'][i] // 2
        y = data['top'][i] + data['height'][i] // 2

        elements.append({
            "text": text,
            "x": x,
            "y": y,
            "confidence": round(conf / 100, 2)
        })

    return elements
