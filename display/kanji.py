from PIL import Image, ImageDraw, ImageFont
from luma.oled.device import sh1106

FONT_PATH = "display/hkhigerei/hkhigerei.ttf"


def display_kanji(
    kanji: str, font_size: int, image_width: int, image_height: int
) -> Image.Image:
    kanji = kanji[0]
    pil_font = ImageFont.truetype(FONT_PATH, size=font_size, encoding="unic")
    text_width, text_height = pil_font.getbbox(kanji)[2:]
    im_canvas = Image.new("RGB", [font_size, font_size], (255, 255, 255))

    draw = ImageDraw.Draw(im_canvas)
    offset = ((font_size - text_width) // 2, (font_size - text_height) // 2)
    white = "#000000"
    draw.text(offset, kanji, font=pil_font, fill=white)

    im_canvas.resize((image_width, image_height), Image.Resampling.LANCZOS)
    return im_canvas


def main():
    device = sh1106(width=520, height=520)
    assert device, "Device not found"

    cols = device.width
    rows = device.height

    while True:
        kanji = input("Enter Kanji:")
        kanji_image = display_kanji(kanji, 25, cols, rows)
        device.display(kanji_image)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
