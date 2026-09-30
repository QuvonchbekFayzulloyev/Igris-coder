# -*- coding: utf-8 -*-
"""V4 docx'dagi 9 rasmni yangi infografika bilan almashtirish + kontakt-sheet."""
import shutil, zipfile, os

SRC = "IGRIS_FULL_AUDIT_V4.docx"
TMP = "IGRIS_FULL_AUDIT_V4_tmp.docx"
NEW_DIR = "_audit_media_new"

# 1) copy zip: replace word/media/imageN.png with new bytes
shutil.copy(SRC, TMP)
zin = zipfile.ZipFile(SRC, "r")
names = zin.namelist()
data = {}
for n in names:
    if n.startswith("word/media/image") and n.endswith(".png"):
        base = os.path.basename(n)
        newp = os.path.join(NEW_DIR, base)
        if os.path.exists(newp):
            data[n] = open(newp, "rb").read()
            print("replaced", n, "->", os.path.getsize(newp), "bytes")
        else:
            data[n] = zin.read(n)
    else:
        data[n] = zin.read(n)
zin.close()

with zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as zout:
    for n, d in data.items():
        zout.writestr(n, d)
print("V4 updated ->", TMP)

# 2) contact sheet for visual check
from PIL import Image
os.makedirs("_audit_media_new", exist_ok=True)
files = [os.path.join(NEW_DIR, f"image{i}.png") for i in range(1, 10)]
imgs = [Image.open(f).convert("RGB") for f in files]
w, h = imgs[0].size
cols, rows = 3, 3
sheet = Image.new("RGB", (cols * w + 20, rows * h + 20), (20, 20, 26))
for i, im in enumerate(imgs):
    r, c = divmod(i, cols)
    sheet.paste(im, (c * w + 5, r * h + 5))
sheet.save("_audit_media_new/contact_sheet.png")
print("contact sheet saved")
