# Maakt assets/icon.png + assets/icon.ico voor DraveShopBuddy.
# Eigen ontwerp: paarse boodschappentas met een drakenoog, een gouden prijskaartje en een vergrootglas.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). GNU GPL v3.0. Pillow nodig.
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HIER = os.path.dirname(os.path.abspath(__file__))
N = 512
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((16, 16, N - 16, N - 16), radius=100, fill=(22, 19, 31, 255), outline=(127, 119, 221, 255), width=12)

# gloed
gl = Image.new("RGBA", (N, N), (0, 0, 0, 0))
ImageDraw.Draw(gl).ellipse((90, 120, 420, 450), fill=(127, 119, 221, 110))
img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(45)))
d = ImageDraw.Draw(img)

# tas
d.polygon([(118, 200), (362, 200), (390, 440), (90, 440)], fill=(127, 119, 221, 255))
d.polygon([(118, 200), (362, 200), (368, 236), (112, 236)], fill=(181, 156, 255, 255))
d.arc((170, 110, 310, 270), 180, 360, fill=(239, 234, 255, 255), width=18)
# drakenoog op de tas
d.ellipse((168, 280, 312, 390), fill=(255, 200, 87, 255))
d.ellipse((180, 290, 300, 380), fill=(255, 166, 40, 255))
d.ellipse((228, 290, 252, 380), fill=(22, 19, 31, 255))
d.ellipse((200, 302, 216, 318), fill=(255, 255, 255, 230))

# gouden prijskaartje rechtsboven
tag = Image.new("RGBA", (N, N), (0, 0, 0, 0))
t = ImageDraw.Draw(tag)
t.polygon([(330, 70), (450, 70), (450, 190), (390, 230), (330, 190)], fill=(255, 200, 87, 255))
t.ellipse((380, 84, 400, 104), fill=(22, 19, 31, 255))
try:
    f = ImageFont.truetype("arialbd.ttf", 92)
except Exception:
    try:
        f = ImageFont.truetype("DejaVuSans-Bold.ttf", 92)
    except Exception:
        f = ImageFont.load_default()
t.text((390, 160), "€", font=f, fill=(22, 19, 31, 255), anchor="mm")
tag = tag.rotate(-12, center=(390, 150), resample=Image.BICUBIC)
img = Image.alpha_composite(img, tag)
d = ImageDraw.Draw(img)

# vergrootglas linksonder
d.ellipse((40, 330, 160, 450), outline=(239, 234, 255, 255), width=16)
d.line([(150, 440), (196, 486)], fill=(239, 234, 255, 255), width=24)

os.makedirs(os.path.join(HIER, "assets"), exist_ok=True)
img.save(os.path.join(HIER, "assets", "icon.png"))
img.save(os.path.join(HIER, "assets", "icon.ico"), format="ICO",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icoon klaar")
