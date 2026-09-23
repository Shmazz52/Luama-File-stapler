# -*- coding: utf-8 -*-
"""
Иконка Luama: контурная лама (iconscout) на тёмном фоне с ромбовой
решёткой. Экспорт: icon.ico, icon.png, llama_gui.png (для шапки GUI).
"""
from PIL import Image, ImageDraw

S = 512
STEP = 42
LINE = (48, 50, 68)

ACCENT = (124, 108, 255, 255)


def draw_lattice(d, w, h):
    for k in range(-h, w + h, STEP):
        d.line([(k, 0), (k + h, h)], fill=LINE, width=2)
        d.line([(k, 0), (k - h, h)], fill=LINE, width=2)


# ---------- загружаем скачанную ламу ----------
llama_src = Image.open("llama_raw.png").convert("RGBA")

# перекрашиваем чёрный контур в фиолетовый акцент, сохраняя альфу
px = llama_src.load()
w, h = llama_src.size
colored = Image.new("RGBA", llama_src.size)
cpx = colored.load()
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a > 0:
            # сила = насколько тёмный пиксель (контур)
            darkness = 255 - r
            if darkness > 30:
                # контур -> фиолетовый
                cpx[x, y] = (124, 108, 255, a)
            else:
                cpx[x, y] = (240, 236, 255, a)  # светлая заливка

# масштабируем до нужного размера
llama = colored.resize((380, 380), Image.LANCZOS)

# ================= ИКОНКА =================
bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(bg).rounded_rectangle([12, 12, S - 12, S - 12], radius=110, fill=(16, 17, 22, 255))

lattice_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
draw_lattice(ImageDraw.Draw(lattice_img), S, S)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([12, 12, S - 12, S - 12], radius=110, fill=255)

img = bg.copy()
img.paste(lattice_img, (0, 0), mask)
img.alpha_composite(llama, ((S - 380) // 2, (S - 380) // 2))

img.save("icon.png")
img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

# ---------- версия для шапки GUI (маленькая, светлая) ----------
gui_llama = colored.resize((40, 40), Image.LANCZOS)
gui_llama.save("llama_gui.png")

print("icon.ico / icon.png / llama_gui.png created")
