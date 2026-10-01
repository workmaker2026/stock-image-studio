from PIL import Image

RESIZE_PRESETS = {
    "2000": 2000,
    "3000": 3000,
    "4000": 4000,
}


def resize(src_path, dest_path, long_edge):
    img = Image.open(src_path)
    w, h = img.size
    scale = long_edge / max(w, h)
    if scale < 1:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    img.save(dest_path, optimize=True)


def optimize(src_path, dest_path):
    img = Image.open(src_path)
    img.save(dest_path, optimize=True, compress_level=9)
