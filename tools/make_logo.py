"""Renders static/logo.png (and logo-64.png) from the same brain drawn in the hero art."""
import sys
from PIL import Image
import hero_art as A
import interior as I

def main(out_dir):
    img = Image.new("RGBA", (A.W, A.H), (0, 0, 0, 0))
    cx, cy, size = A.W / 2, A.H / 2, 1400
    I.brain(img, cx, cy, size, aura_scale=0.82)
    box = img.getbbox()
    pad = 6
    crop = img.crop((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad))
    w, h = crop.size
    side = max(w, h)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(crop, ((side - w) // 2, (side - h) // 2))
    sq.resize((256, 256), Image.LANCZOS).save(f"{out_dir}/logo.png", optimize=True)
    sq.resize((64, 64), Image.LANCZOS).save(f"{out_dir}/logo-64.png", optimize=True)
    sq.resize((180, 180), Image.LANCZOS).save(f"{out_dir}/logo-180.png", optimize=True)

if __name__ == "__main__":
    main(sys.argv[1])
