from io import BytesIO

from django.conf import settings
from django.http import FileResponse
from PIL import Image, ImageDraw, ImageFont


def render_card(snapshot, url):
    font_path = settings.BASE_DIR / 'static/fonts/NotoNastaliqUrdu.ttf'
    poetry = ImageFont.truetype(str(font_path), 51)
    credit = ImageFont.truetype(str(font_path), 35)
    latin = ImageFont.truetype(str(font_path), 25)
    width = 1080
    paper = '#f5ead4'
    ink = '#302821'
    accent = '#783b30'
    margin = 88
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))

    def wrapped(text, font):
        line = ''
        for word in text.split():
            candidate = f'{line} {word}'.strip()
            if measure.textlength(candidate, font=font) <= width - 2 * margin:
                line = candidate
                continue
            if line:
                yield line
            line = ''
            for char in word:
                if line and measure.textlength(line + char, font=font) > width - 2 * margin:
                    yield line
                    line = ''
                line += char
        if line:
            yield line

    lines = []
    for _, first, second in snapshot['rows']:
        lines.extend((part, poetry, ink, 98) for text in (first, second) for part in wrapped(text, poetry))
        lines.append(('', poetry, ink, 28))
    lines.extend((line, credit, accent, 68) for line in wrapped(snapshot['author'], credit))
    lines.extend((line, latin, ink, 42) for line in wrapped(url, latin))
    height = 180 + sum(gap for _, _, _, gap in lines)
    image = Image.new('RGB', (width, height), paper)
    draw = ImageDraw.Draw(image)
    draw.rectangle((38, 38, width - 38, height - 38), outline=accent, width=3)
    draw.line((margin, 64, width - margin, 64), fill=accent, width=2)
    y = 90
    for line, font, color, gap in lines:
        draw.text((width / 2, y), line, anchor='mt', font=font, fill=color)
        y += gap
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename='divannameh-verse.png', content_type='image/png')
