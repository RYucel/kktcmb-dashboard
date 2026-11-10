# -*- coding: utf-8 -*-
"""OKLCH -> sRGB hex + kontrast. Grafik paleti icin."""
import math, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def oklch_to_srgb(L, C, H):
    # OKLCH -> OKLab
    h = math.radians(H)
    a, b = C * math.cos(h), C * math.sin(h)
    # OKLab -> LMS
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3
    # LMS -> linear sRGB
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    def enc(x):
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * (x ** (1/2.4)) - 0.055
    return tuple(round(enc(v) * 255) for v in (r, g, bb))

def lum(rgb):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def hexs(rgb):
    return "#%02x%02x%02x" % rgb

paper = oklch_to_srgb(0.175, 0.014, 268)
paper2 = oklch_to_srgb(0.21, 0.016, 268)
paper3 = oklch_to_srgb(0.25, 0.017, 268)
print("paper", hexs(paper), "paper2", hexs(paper2), "paper3", hexs(paper3))
print()

pal = [
    ("p86", 0.86, 0.075, 274),
    ("a88", 0.88, 0.070, 62),
    ("p70", 0.70, 0.110, 274),
    ("d82", 0.82, 0.085, 330),
    ("p78", 0.78, 0.100, 274),
    ("a68", 0.68, 0.115, 62),
    ("p58", 0.58, 0.120, 274),
    ("d64", 0.64, 0.120, 330),
    ("p62", 0.62, 0.120, 274),
    ("a78", 0.78, 0.100, 62),
    ("p50", 0.50, 0.125, 274),
    ("d72", 0.72, 0.105, 330),
    ("a58", 0.58, 0.120, 62),
    ("d54", 0.54, 0.115, 330),
]
for name, L, C, H in pal:
    rgb = oklch_to_srgb(L, C, H)
    print(f"{name}: oklch({L*100:.0f}% {C:.3f} {H}) -> {hexs(rgb)}  "
          f"vs paper2 {contrast(rgb, paper2):.1f}:1  vs paper {contrast(rgb, paper):.1f}:1")

print()
for name, L, C, H in [("ink", .96, .006, 75), ("ink2", .85, .010, 262),
                      ("muted", .70, .016, 262), ("accent", .77, .10, 274),
                      ("accent2", .83, .095, 62), ("rule", .30, .016, 266)]:
    rgb = oklch_to_srgb(L, C, H)
    print(f"{name}: {hexs(rgb)}  vs paper {contrast(rgb, paper):.1f}:1  vs paper2 {contrast(rgb, paper2):.1f}:1")
