# -*- coding: utf-8 -*-
"""Google Fonts CSS'ini ayristirip Wix Madefor woff2 alt kumelerini indirir."""
import re, sys, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSS = Path(r"C:\Users\SuperComputers\AppData\Local\Temp\opencode\wix.css")
OUT = Path(r"E:\Projeler\KKTCMB\assets\fonts")
OUT.mkdir(parents=True, exist_ok=True)

css = CSS.read_text(encoding="utf-8")
blocks = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
print("font-face blok sayisi:", len(blocks))

wanted = {}
for b in blocks:
    fam = re.search(r"font-family:\s*'([^']+)'", b)
    wt = re.search(r"font-weight:\s*(\d+)", b)
    ur = re.search(r"unicode-range:\s*([^;]+);", b)
    src = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", b)
    if not (fam and wt and ur and src):
        continue
    rng = ur.group(1)
    if "U+0100-02BA" in rng:
        sub = "latin-ext"
    elif "U+0000-00FF" in rng:
        sub = "latin"
    else:
        continue
    fam_slug = "display" if "Display" in fam.group(1) else "text"
    name = f"wix-{fam_slug}-{wt.group(1)}-{sub}.woff2"
    wanted[name] = src.group(1)

for name, url in sorted(wanted.items()):
    dest = OUT / name
    urllib.request.urlretrieve(url, dest)
    print(f"  {name}: {dest.stat().st_size/1024:.1f} KB")

print(f"\n{len(wanted)} dosya -> {OUT}")
