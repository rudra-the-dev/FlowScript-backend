import base64
import io
from PIL import Image, ImageDraw, ImageFont

def draw_overlay(screenshot_b64, elements):
    img_bytes = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        small_font = font

    for el in elements:
        eid = el.get('id')
        bounds = el.get('bounds')
        clickable = el.get('clickable', False)

        if not bounds:
            x, y = el.get('x', 0), el.get('y', 0)
            bounds = [x - 40, y - 20, x + 40, y + 20]

        x1, y1, x2, y2 = bounds[0], bounds[1], bounds[2], bounds[3]
        color = '#00FF00' if clickable else '#FF4444'

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        label_bg = [x1, y1 - 32, x1 + 42, y1]
        draw.rectangle(label_bg, fill=color)
        draw.text((x1 + 4, y1 - 30), str(eid), fill='black', font=font)

    out = io.BytesIO()
    img.save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()
