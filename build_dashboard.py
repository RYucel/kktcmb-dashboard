#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data/kktcmb.csv + template.html -> output/kktcmb_dashboard.html
Tek dosya, cevrimdisi calisan Plotly dashboard uretir.

Kullanim: python build_dashboard.py
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "data" / "kktcmb.csv"
TEMPLATE = ROOT / "template.html"
META_SRC = ROOT / "data" / "scrape_meta.json"
OUT = ROOT / "output" / "kktcmb_dashboard.html"
KAYNAK_URL = "https://mb.gov.ct.tr/tr/veriler/istatistikiveriler/para-banka-eski"

TR_MAP = {"ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
          "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u"}

FONTS = ROOT / "assets" / "fonts"
LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,"
         "U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,"
         "U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,"
             "U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,"
             "U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")

# Grafiklerde ve ciplerde yer kazanmak icin kisa adlar
KISA_ADLAR = {
    "Diğer Krediler": "Diğer krediler",
    "Diğer Yatırım Kredileri": "Diğer yatırım",
    "Fon Kaynaklı Krediler": "Fon kaynaklı",
    "KKTC Merkez Bankası Aracılığıyle Kul. Krd.": "MB aracılığıyla",
    "KKTC Merkez Bankası Kaynaklı Krediler": "MB kaynaklı",
    "Kredi Kartları": "Kredi kartları",
    "Müşteri Adına Menkul Değer Alım Kredileri": "Menkul değer alım",
    "Tüketici Kredileri": "Tüketici",
    "İhracat Garantili Yatırım Kredileri": "İhracat garantili",
    "İhracat Kredileri": "İhracat",
    "İhtisas Kredileri": "İhtisas",
    "İskonto ve İştira Senetleri": "İskonto ve iştira",
    "İthalat Kredileri": "İthalat",
    "İşletme Kredileri": "İşletme",
    "Diğer Mevduat": "Diğer mevduat",
    "1 Ay Vadeli": "1 ay vadeli",
    "3 Ay Vadeli": "3 ay vadeli",
    "6 Ay Vadeli": "6 ay vadeli",
    "1 Yıl Vadeli": "1 yıl vadeli",
    "TOPLAM": "Toplam",
}


def kisa_ad(ad: str) -> str:
    return KISA_ADLAR.get(ad, ad)


def font_css() -> str:
    """assets/fonts altindaki woff2 dosyalarini base64 @font-face olarak gömer."""
    aileler = [
        ("Wix Madefor Display", 500, "wix-display-500"),
        ("Wix Madefor Text", 400, "wix-text-400"),
        ("Wix Madefor Text", 500, "wix-text-500"),
    ]
    parcalar = []
    eksik = []
    for aile, agirlik, slug in aileler:
        for alt, aralik in (("latin", LATIN), ("latin-ext", LATIN_EXT)):
            yol = FONTS / f"{slug}-{alt}.woff2"
            if not yol.exists():
                eksik.append(yol.name)
                continue
            b64 = base64.b64encode(yol.read_bytes()).decode("ascii")
            parcalar.append(
                '@font-face{font-family:"%s"; font-style:normal; font-weight:%d; '
                'font-display:swap; src:url(data:font/woff2;base64,%s) format("woff2"); '
                'unicode-range:%s}' % (aile, agirlik, b64, aralik))
    if eksik:
        print(f"[UYARI] Eksik font dosyalari: {eksik} (sistem fontuna duser)")
    if parcalar:
        print(f"  font: {len(parcalar)} @font-face gomuldu "
              f"({sum(len(p) for p in parcalar)/1024:.0f} KB base64)")
    return "\n".join(parcalar)


def slugify(s: str) -> str:
    s2 = "".join(TR_MAP.get(c, c) for c in s)
    return re.sub(r"[^A-Za-z0-9]+", "_", s2).strip("_").lower()


def seri(sub: pd.DataFrame) -> dict:
    """Bir (kategori) alt kumesinden {d:[tarih...], v:[deger...]} serisi uretir."""
    sub = sub.dropna(subset=["deger"]).sort_values("tarih")
    if sub.duplicated("tarih").any():
        sub = sub[~sub.duplicated("tarih")]
    return {"d": sub["tarih"].tolist(),
            "v": [round(float(x), 2) for x in sub["deger"]]}


def son_deger(s: dict):
    return s["v"][-1] if s["v"] else None


def main() -> int:
    if not CSV.exists():
        print("data/kktcmb.csv yok — once 'python scrape.py' calistirin.")
        return 1

    df = pd.read_csv(CSV, dtype={"tarih": str})
    df["deger"] = pd.to_numeric(df["deger"], errors="coerce")

    # Birim normalizasyonu: her sey BİN TL bazina (MİLYON TL gorursek x1000)
    birimler = df["birim"].dropna().unique()
    for b in birimler:
        if "MİLYON" in str(b).upper():
            mask = df["birim"] == b
            df.loc[mask, "deger"] = df.loc[mask, "deger"] * 1000
            print(f"[UYARI] {b} birimli {int(mask.sum())} satir BİN TL'ye cevrildi (x1000).")
        elif str(b).strip().upper() not in ("BİN TL", "BIN TL"):
            print(f"[UYARI] Bilinmeyen birim: {b!r} (dokunulmadi).")

    DATA: dict[str, dict] = {}

    def kategori_seri(table, kirim, kategori, seri_id):
        sub = df[(df["table"] == table) & (df["kirim"] == kirim) & (df["kategori"] == kategori)]
        DATA[seri_id] = seri(sub)

    def tablo(table, kirim):
        return df[(df["table"] == table) & (df["kirim"] == kirim)]

    # ------------------------------------------------ KREDILER (sektore gore)
    kredi_toplam_satiri = None
    for k in tablo("kredi_sektor", "toplam")["kategori"].unique():
        if str(k).startswith("Toplam Krediler"):
            kredi_toplam_satiri = k
            break
    if not kredi_toplam_satiri:
        print("[HATA] 'Toplam Krediler' satiri bulunamadi!")
        return 1

    kredi_sektorleri = []  # (slug, ad) — toplam satiri haric
    for k in tablo("kredi_sektor", "toplam")["kategori"].unique():
        if k != kredi_toplam_satiri:
            kredi_sektorleri.append((slugify(k), k))

    for kirim, suf in [("toplam", ""), ("tp", "_tp"), ("yp", "_yp")]:
        kategori_seri("kredi_sektor", kirim, kredi_toplam_satiri, f"kredi_total{suf}")
        for slug, ad in kredi_sektorleri:
            kategori_seri("kredi_sektor", kirim, ad, f"ks{suf}_{slug}")

    # ------------------------------------------------ KREDI VADE + KAMU/OZEL
    kategori_seri("kredi_vade", "toplam", "Kısa Vadeli", "kredi_vade_kisa")
    kategori_seri("kredi_vade", "toplam", "Orta Ve Uzun Vadeli", "kredi_vade_uzun")
    kategori_seri("kredi_vade", "toplam", "TOPLAM", "kredi_vade_toplam")
    kategori_seri("kredi_kamu_ozel", "toplam", "Kamu Kredileri", "kredi_kamu")
    kategori_seri("kredi_kamu_ozel", "toplam", "Özel Krediler", "kredi_ozel")
    kategori_seri("kredi_kamu_ozel", "toplam", "TOPLAM", "kredi_ko_toplam")

    # ------------------------------------------------ MEVDUAT (ture gore)
    # 2014 oncesi: TOPLAM = mevduat + bankalar (ayri GENEL TOPLAM yok)
    # 2014 sonrasi: TOPLAM = mevduat (bankalar haric), GENEL TOPLAM = dahil
    MEV_TURLER = ["Resmi", "Ticari", "Tasarruf", "Diğer Mevduat"]
    for kirim, suf in [("toplam", ""), ("tp", "_tp"), ("yp", "_yp")]:
        haric, genel, bankalar = {}, {}, {}
        for yil, ys in tablo("mevduat_tur", kirim).groupby("yil"):
            kats = set(ys["kategori"])
            yeni_yapi = "GENEL TOPLAM" in kats
            bank_rows = ys[ys["kategori"].str.startswith("Bankalar")].set_index("tarih")["deger"]
            toplam_rows = ys[ys["kategori"] == "TOPLAM"].set_index("tarih")["deger"]
            genel_rows = (ys[ys["kategori"] == "GENEL TOPLAM"].set_index("tarih")["deger"]
                          if yeni_yapi else None)
            for tarih, t in toplam_rows.items():
                if pd.isna(t):
                    continue
                b = bank_rows.get(tarih)
                if yeni_yapi:
                    haric[tarih] = t
                    g = genel_rows.get(tarih) if genel_rows is not None else None
                    genel[tarih] = g if (g is not None and not pd.isna(g)) else None
                    bankalar[tarih] = b if (b is not None and not pd.isna(b)) else None
                else:
                    bankalar[tarih] = b if (b is not None and not pd.isna(b)) else None
                    haric[tarih] = (t - b) if (b is not None and not pd.isna(b)) else None
                    genel[tarih] = t
        for ad_hedef, sozluk in [("haric", haric), ("genel", genel), ("bankalar", bankalar)]:
            tarihler = sorted([d for d, v in sozluk.items() if v is not None and not pd.isna(v)])
            DATA[f"mev_{ad_hedef}{suf}"] = {
                "d": tarihler,
                "v": [round(float(sozluk[d]), 2) for d in tarihler],
            }
        for k in MEV_TURLER:
            kategori_seri("mevduat_tur", kirim, k, f"mt{suf}_{slugify(k)}")

    # ------------------------------------------------ MEVDUAT (vadeye gore)
    MEV_VADELER = ["Vadesiz", "1 Ay Vadeli", "3 Ay Vadeli", "6 Ay Vadeli", "1 Yıl Vadeli"]
    for kirim, suf in [("toplam", ""), ("tp", "_tp"), ("yp", "_yp")]:
        for k in MEV_VADELER:
            kategori_seri("mevduat_vade", kirim, k, f"mv{suf}_{slugify(k)}")
        kategori_seri("mevduat_vade", kirim, "TOPLAM", f"mv{suf}_toplam")

    # ------------------------------------------------ META
    kredi_sek_list = []
    for slug, ad in kredi_sektorleri:
        sv = son_deger(DATA.get(f"ks_{slug}", {"v": []})) or 0
        kredi_sek_list.append({"slug": slug, "ad": kisa_ad(ad), "tam": ad, "sonDeger": sv,
                               "varsayilan": sv > 0})
    kredi_sek_list.sort(key=lambda x: -x["sonDeger"])

    mev_tur_list = []
    for k in MEV_TURLER:
        sv = son_deger(DATA.get(f"mt_{slugify(k)}", {"v": []})) or 0
        mev_tur_list.append({"slug": slugify(k), "ad": kisa_ad(k), "tam": k, "sonDeger": sv})
    mev_tur_list.sort(key=lambda x: -x["sonDeger"])

    mev_vade_list = [{"slug": slugify(k), "ad": kisa_ad(k), "varsayilan": True}
                     for k in MEV_VADELER]
    mev_vade_list.append({"slug": "toplam", "ad": "Toplam", "varsayilan": False})

    scrape_zamani = datetime.now().isoformat(timespec="seconds")
    if META_SRC.exists():
        try:
            scrape_zamani = json.loads(META_SRC.read_text(encoding="utf-8")).get(
                "scrape_zamani", scrape_zamani)
        except Exception:  # noqa: BLE001
            pass

    ilk = DATA["kredi_total"]["d"][0][:7]
    son = DATA["kredi_total"]["d"][-1][:7]
    META = {
        "ilkAy": ilk, "sonAy": son,
        "scrapeZamani": scrape_zamani,
        "krediSektorler": kredi_sek_list,
        "mevduatTurler": mev_tur_list,
        "mevduatVadeler": mev_vade_list,
    }

    # ------------------------------------------------ tutarlilik kontrolleri
    print("---- Tutarlilik kontrolleri ----")
    sorun = 0

    def kontrol(ad, sart, detay):
        nonlocal sorun
        dur = "OK " if sart else "SORUN"
        if not sart:
            sorun += 1
        print(f"  [{dur}] {ad}: {detay}")

    km = {d: v for d, v in zip(DATA["kredi_total"]["d"], DATA["kredi_total"]["v"])}
    kt = {d: v for d, v in zip(DATA["kredi_total_tp"]["d"], DATA["kredi_total_tp"]["v"])}
    ky = {d: v for d, v in zip(DATA["kredi_total_yp"]["d"], DATA["kredi_total_yp"]["v"])}
    ortak = [d for d in km if d in kt and d in ky]
    fark = max(abs(km[d] - kt[d] - ky[d]) for d in ortak) if ortak else None
    kontrol("Kredi TP+YP=Toplam", fark is not None and fark < 1,
            f"maks fark={fark} bin TL ({len(ortak)} ortak ay)")

    hm = {d: v for d, v in zip(DATA["mev_haric"]["d"], DATA["mev_haric"]["v"])}
    kontrol("Mevduat (haric) pozitif", all(v > 0 for v in hm.values()),
            f"min={min(hm.values()) if hm else None}")

    # tur kategorileri haric seriyi vermelidir
    tur_sum_hata = []
    for d in list(hm.keys())[::24]:  # ornekleme: 2 yilda bir
        toplam = sum(DATA[f"mt_{slugify(k)}"].get("d") and
                     (dict(zip(DATA[f"mt_{slugify(k)}"]["d"], DATA[f"mt_{slugify(k)}"]["v"])).get(d) or 0)
                     for k in MEV_TURLER)
        if hm[d] and abs(toplam - hm[d]) > max(1.0, hm[d] * 1e-4):
            tur_sum_hata.append((d, toplam, hm[d]))
    kontrol("Mevduat türleri toplamı = Mevduat(haric)", not tur_sum_hata,
            f"örneklemede {len(tur_sum_hata)} sapma" + (f" ilk: {tur_sum_hata[:2]}" if tur_sum_hata else ""))

    eksik = [k for k, s in DATA.items() if not s["v"]]
    kontrol("Boş seri yok", not eksik, f"boş: {eksik[:8]}" if eksik else f"{len(DATA)} seri dolu")

    n_puan = sum(len(s["d"]) for s in DATA.values())
    print(f"  Toplam: {len(DATA)} seri, {n_puan} veri noktasi, aralik {ilk} - {son}")
    if sorun:
        print(f"  !! {sorun} kontrol sorunlu — yine de uretime devam ediliyor.")

    # ------------------------------------------------ HTML uret
    tpl = TEMPLATE.read_text(encoding="utf-8")
    plotly_yolu = os.path.join(os.path.dirname(plotly.__file__), "package_data", "plotly.min.js")
    if os.path.exists(plotly_yolu):
        plotly_js = Path(plotly_yolu).read_text(encoding="utf-8")
        plotly_kaynak = f"inline ({os.path.getsize(plotly_yolu)/1e6:.1f} MB)"
    else:
        plotly_js = 'document.write("<script src=\\"https://cdn.plot.ly/plotly-2.35.2.min.js\\"><\\/script>");'
        plotly_kaynak = "CDN (offline calismaz!)"
        print("[UYARI] plotly.min.js bulunamadi, CDN fallback yazildi.")

    html = (tpl
            .replace("__FONTCSS__", font_css())
            .replace("__PLOTLYJS__", plotly_js)
            .replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
            .replace("__META__", json.dumps(META, ensure_ascii=False, separators=(",", ":")))
            .replace("__KAYNAKURL__", KAYNAK_URL))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"\nBITTI -> {OUT}")
    print(f"  boyut: {OUT.stat().st_size/1e6:.1f} MB | plotly: {plotly_kaynak}")

    # Vercel vb. statik hosting icin kopya: site/index.html
    SITE = ROOT / "site" / "index.html"
    SITE.parent.mkdir(parents=True, exist_ok=True)
    SITE.write_text(html, encoding="utf-8")
    print(f"  deploy kopyasi -> {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
