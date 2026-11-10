#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KKTC Merkez Bankasi - Para Banka veri toplayici
================================================
Kaynak : https://mb.gov.ct.tr/tr/veriler/istatistikiveriler/para-banka-eski
Cikti  : data/kktcmb.csv (tidy/long) + data/scrape_meta.json (QA bilgisi)

Kullanim:
  python scrape.py                 normal calisma (cache + TTL; icinde bulunulan yil hep taze)
  python scrape.py --force         tum sayfalari yeniden indir
  python scrape.py --offline       sadece cache kullan (ag istegi yok)
  python scrape.py --ttl-days 3    tum TTL'leri override et

Not: Yeni yil (orn. 2027) node'lari siteye eklendiginde liste sayfasindan
otomatik kesfedilir; ayrica scrape.py icindeki HARDCODED_NODES guncellenebilir.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Windows konsolunda Turkce karakter sorununu onle
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://mb.gov.ct.tr"
LISTING_URLS = [
    "/tr/veriler/istatistikiveriler/para-banka-eski",
    "/tr/veriler/istatistikiveriler/parabanka",
]

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
DATA_CSV = ROOT / "data" / "kktcmb.csv"
META_JSON = ROOT / "data" / "scrape_meta.json"

AYLAR = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN",
         "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
AY_NO = {a: i + 1 for i, a in enumerate(AYLAR)}

# Liste sayfasi basligi (normallestirilmis) -> (table, kirim)
FAMILY_MATCH = {
    "krediler - sektörlere göre (toplam)": ("kredi_sektor", "toplam"),
    "krediler - sektörlere göre (tp)": ("kredi_sektor", "tp"),
    "krediler - sektörlere göre (yp)": ("kredi_sektor", "yp"),
    "krediler - vadelere göre": ("kredi_vade", "toplam"),
    "krediler - kamu özel ayrımı": ("kredi_kamu_ozel", "toplam"),
    "mevduat - vade gruplarına göre dağılım (toplam)": ("mevduat_vade", "toplam"),
    "mevduat - vade gruplarına göre dağılım (tp)": ("mevduat_vade", "tp"),
    "mevduat - vade gruplarına göre dağılım (yp)": ("mevduat_vade", "yp"),
    "mevduat - türlerine göre dağılım (toplam)": ("mevduat_tur", "toplam"),
    "mevduat - türlerine göre dağılım (tp)": ("mevduat_tur", "tp"),
    "mevduat - türlerine göre dağılım (yp)": ("mevduat_tur", "yp"),
}

# Dogrulanmis yedek node haritasi (kesif basarisiz olursa kullanilir;
# kesif calisirsa yeni/yeni yil node'lari otomatik eklenir)
HARDCODED_NODES = {
    ("kredi_sektor", "toplam"): {2010: [542], 2011: [545], 2012: [540], 2013: [535], 2014: [1222], 2015: [1765], 2016: [2373], 2017: [2800], 2018: [3123], 2019: [3914], 2020: [3928], 2021: [4128], 2022: [4474], 2023: [4894], 2024: [5289], 2025: [5704], 2026: [6061]},
    ("kredi_sektor", "tp"): {2010: [554], 2011: [553], 2012: [547], 2013: [546], 2014: [1223], 2015: [1766], 2016: [2374], 2017: [2801], 2018: [3124], 2019: [3915], 2020: [3929], 2021: [4129], 2022: [4475], 2023: [4895], 2024: [5290], 2025: [5705], 2026: [6062]},
    ("kredi_sektor", "yp"): {2010: [559], 2011: [558], 2012: [557], 2013: [555], 2014: [1224], 2015: [1767], 2016: [2375], 2017: [2802], 2018: [3125], 2019: [3916], 2020: [3930], 2021: [4130], 2022: [4476], 2023: [4896], 2024: [5291], 2025: [5706], 2026: [6063]},
    ("kredi_vade", "toplam"): {2010: [563], 2011: [562], 2012: [561], 2013: [560], 2014: [1225], 2015: [1768], 2016: [2376], 2017: [2803], 2018: [3126], 2019: [3917], 2020: [3931], 2021: [4131], 2022: [4477], 2023: [4897], 2024: [5292], 2025: [5707], 2026: [6064]},
    ("kredi_kamu_ozel", "toplam"): {2010: [570], 2011: [569], 2012: [568], 2013: [567], 2014: [1226], 2015: [1756], 2016: [2377], 2017: [2804], 2018: [3127], 2019: [3918], 2020: [3932], 2021: [4132], 2022: [4478], 2023: [4898], 2024: [5293], 2025: [5708], 2026: [6065]},
    ("mevduat_tur", "toplam"): {2010: [526], 2011: [525], 2012: [524], 2013: [522], 2014: [1219], 2015: [1762], 2016: [2370], 2017: [2797], 2018: [3120], 2019: [3911], 2020: [3925], 2021: [4125], 2022: [4471], 2023: [4891], 2024: [5286], 2025: [5701], 2026: [6058]},
    ("mevduat_tur", "tp"): {2010: [530], 2011: [529], 2012: [528], 2013: [527], 2014: [1220], 2015: [1763], 2016: [2371], 2017: [2798], 2018: [3121], 2019: [3912], 2020: [3926], 2021: [4126], 2022: [4472], 2023: [4892], 2024: [5287], 2025: [5702], 2026: [6068]},
    ("mevduat_tur", "yp"): {2010: [534], 2011: [533], 2012: [532], 2013: [531], 2014: [1221], 2015: [1764], 2016: [2372], 2017: [2799], 2018: [3122], 2019: [3913], 2020: [3927], 2021: [4127], 2022: [4473], 2023: [4893], 2024: [5288], 2025: [5703], 2026: [6060]},
    ("mevduat_vade", "toplam"): {2010: [463], 2011: [462], 2012: [461], 2013: [395], 2014: [1216], 2015: [1759], 2016: [2367], 2017: [2794], 2018: [3117], 2019: [3908], 2020: [3922], 2021: [4122], 2022: [4468], 2023: [4888], 2024: [5283], 2025: [5698], 2026: [6055, 6076]},
    ("mevduat_vade", "tp"): {2010: [467], 2011: [466], 2012: [465], 2013: [464], 2014: [1217], 2015: [1760], 2016: [2368], 2017: [2795], 2018: [3118], 2019: [3909], 2020: [3923], 2021: [4123], 2022: [4469], 2023: [4889], 2024: [5284], 2025: [5699], 2026: [6056, 6077]},
    ("mevduat_vade", "yp"): {2010: [471], 2011: [470], 2012: [469], 2013: [468], 2014: [1218], 2015: [1761], 2016: [2369], 2017: [2796], 2018: [3119], 2019: [3910], 2020: [3924], 2021: [4124], 2022: [4470], 2023: [4890], 2024: [5285], 2025: [5700], 2026: [6057]},
}

WARNINGS: list[str] = []
STATS = {"fetched": 0, "from_cache": 0, "skipped_offline": 0, "failed": 0}


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  [UYARI] {msg}")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


# ---------------------------------------------------------------- sayi ayristirma
def parse_num(s: str):
    """2010 stili (1.817.058) ve 2026 stili (7,036,594) binlik ayraclari,
    tam sayi, ondalik ve parantezli negatifleri ele alir."""
    s = (s or "").strip().replace("\u00a0", " ").replace(" ", "")
    if not s or s in {"-", "–", "—"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if re.fullmatch(r"-?\d+", s):
        v = float(s)
    elif re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", s):  # binlik ayracli tamsayi
        v = float(s.replace(".", "").replace(",", ""))
    elif re.fullmatch(r"-?\d+[.,]\d{1,2}", s):        # ondalik (1-2 hane)
        v = float(s.replace(",", "."))
    else:
        return None
    return -v if neg else v


# ---------------------------------------------------------------- tablo ayristirma
def row_cells(tr):
    """Bir <tr> icindeki hucreleri (grid_kolon_no, metin) listesi olarak verir.
    colspan hesaba katilir; boylece baslik satirindaki ay eslemesi satirlarla hizalanir."""
    cells, col = [], 0
    for td in tr.find_all("td", recursive=False):
        try:
            span = int(td.get("colspan", 1) or 1)
        except ValueError:
            span = 1
        cells.append((col, td.get_text(" ", strip=True)))
        col += span
    return cells


def parse_page(html: str):
    """Tek yillik MB veri sayfasini ayristirir.
    Donus: (birim, [(kategori, {ay_no: deger}), ...], baslik) veya hata durumunda (None, None, hata)."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup
    tables = main.find_all("table")
    if not tables:
        return None, None, "sayfada tablo yok"
    table = tables[0]
    title = (soup.find("h1").get_text(" ", strip=True)
             if soup.find("h1") else "")
    unit = None
    header_map = None  # {grid_kolon: ay_no}
    rows = []
    for tr in table.find_all("tr"):
        cells = row_cells(tr)
        if not cells:
            continue
        joined = " ".join(tx for _, tx in cells).upper()
        if "PARA B" in joined and unit is None:
            m = re.search(r"PARA\s*BİRİMİ\s*:?\s*(.+)$", norm(joined))
            unit = norm(m.group(1)) if m else norm(joined)
            continue
        found = {}
        for c, tx in cells:
            key = tx.upper().replace("İ", "İ").strip()
            if key in AY_NO:
                found[c] = AY_NO[key]
        if len(found) >= 6:  # ay baslikli satir
            header_map = found
            continue
        if header_map is None:
            continue  # basliklardan onceki satirlar (tablo adi vb.)
        # kategori = ayirici olmayan ilk hucre (kredi tablolarindaki satir numarasini atla)
        kategori = None
        for c, tx in cells:
            if c in header_map:
                break
            if tx and not re.fullmatch(r"[\d\.\-]+", tx):
                kategori = norm(tx)
                break
        if not kategori:
            continue
        bycol = dict(cells)
        vals = {ay: parse_num(bycol.get(c, "")) for c, ay in header_map.items()}
        rows.append((kategori, vals))
    if header_map is None:
        return None, None, "ay baslikli satir bulunamadi"
    if not rows:
        return None, None, "veri satiri bulunamadi"
    return (unit, rows, title), None


# ---------------------------------------------------------------- ag ve cache
def decode(resp: requests.Response) -> str:
    enc = (resp.encoding or "").lower()
    if enc not in ("utf-8", "utf8"):
        return resp.content.decode("utf-8", errors="replace")
    return resp.text


def ttl_for(year: int, ttl_override) -> int:
    if ttl_override is not None:
        return int(ttl_override) * 86400
    today = date.today()
    if year >= today.year:
        return 1 * 86400            # icinde bulunulan yil: her gun taze
    if year == today.year - 1:
        return 30 * 86400           # onceki yil: revizyon ihtimali
    return 365 * 86400              # eski yillar: statik


def cached_fetch(session, url: str, cache_path: Path, ttl: int,
                 force: bool, offline: bool):
    """Cache'li sayfa getirme. Donus: (html, kaynak) -- kaynak: 'ag'|'cache'|None"""
    if cache_path.exists() and not force:
        age = time.time() - cache_path.stat().st_mtime
        if offline or age < ttl:
            STATS["from_cache"] += 1
            return cache_path.read_text(encoding="utf-8", errors="replace"), "cache"
    if offline:
        STATS["skipped_offline"] += 1
        return None, None
    last_err = None
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            html = decode(r)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(html, encoding="utf-8")
            STATS["fetched"] += 1
            return html, "ag"
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1 + 2 * attempt)
    STATS["failed"] += 1
    warn(f"Indirme hatasi {url}: {last_err}")
    return None, None


# ---------------------------------------------------------------- kesif
def discover_nodes(session, force: bool, offline: bool):
    """Liste sayfasindan (tablo ailesi -> yil -> node listesi) haritasi cikarir."""
    for path in LISTING_URLS:
        cache = RAW_DIR / "_listing" / (path.strip("/").replace("/", "_") + ".html")
        html, _ = cached_fetch(session, BASE + path, cache, 86400, force, offline)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        main = soup.find("main") or soup
        container = main.find("div", class_="view-content") or main
        result = {}
        for h3 in container.find_all("h3"):
            key = FAMILY_MATCH.get(norm(h3.get_text(" ", strip=True)).lower())
            if not key:
                continue
            grid = h3.find_next_sibling("div")
            if grid is None:
                continue
            yearmap: dict[int, list[int]] = {}
            for a in grid.find_all("a"):
                ytxt = a.get_text(strip=True)
                m = re.search(r"/tr/node/(\d+)", a.get("href", "") or "")
                if not m or not ytxt.isdigit():
                    continue
                y, node = int(ytxt), int(m.group(1))
                lst = yearmap.setdefault(y, [])
                if node not in lst:
                    lst.append(node)
            if yearmap:
                result[key] = yearmap
        if len(result) >= 5:
            return result
    return None


def merge_maps(discovered, hardcoded):
    """Kesif sonucunu yedek haritanin ustune yazar; yeni ogeleri raporlar."""
    merged = {k: dict(v) for k, v in hardcoded.items()}
    if not discovered:
        warn("Liste sayfasindan node kesfi yapilamadi; yedek (hardcoded) harita kullaniliyor.")
        return merged
    for key, yearmap in discovered.items():
        cur = merged.setdefault(key, {})
        for y, nodes in yearmap.items():
            if y not in cur:
                print(f"  [BILGI] Yeni yil kesfedildi: {key[0]}/{key[1]} {y} -> node {nodes}")
            elif set(cur[y]) != set(nodes):
                print(f"  [BILGI] Node farki: {key[0]}/{key[1]} {y} hardcoded={cur[y]} kesif={nodes}")
            cur[y] = nodes
    extra = set(discovered) - set(hardcoded)
    if extra:
        warn(f"Kapsam disi tablo aileleri kesfedildi (atlandi): {sorted(extra)}")
    return merged


# ---------------------------------------------------------------- tek aile-yil cozumu
def resolve_duplicates(items, label):
    """Ayni (tablo, yil) icin birden fazla node varsa en dolu olan secilir.
    items: [{'node', 'unit', 'rows'}]"""
    def nonnull_count(it):
        return sum(1 for _, vals in it["rows"] for v in vals.values() if v is not None)

    best = max(items, key=lambda it: (nonnull_count(it), it["node"]))
    if len(items) > 1:
        for other in items:
            if other["node"] == best["node"]:
                continue
            diff = 0
            for kat, vals in other["rows"]:
                for bkat, bvals in best["rows"]:
                    if bkat == kat:
                        for ay, v in vals.items():
                            bv = bvals.get(ay)
                            if v is not None and bv is not None and abs(v - bv) > 0.5:
                                diff += 1
                        break
            msg = (f"{label}: node {other['node']} ({nonnull_count(other)} dolu deger) yerine "
                   f"node {best['node']} ({nonnull_count(best)} dolu deger) secildi"
                   + (f"; {diff} cakisan deger farkli!" if diff else ""))
            print(f"  [BILGI] {msg}")
            if diff:
                warn(msg)
    return best


# ---------------------------------------------------------------- ana akis
def main() -> int:
    ap = argparse.ArgumentParser(description="KKTC MB Para-Banka veri toplayici")
    ap.add_argument("--force", action="store_true", help="cache'i yok say, her seyi yeniden indir")
    ap.add_argument("--offline", action="store_true", help="ag istegi yapma, sadece cache")
    ap.add_argument("--ttl-days", type=int, default=None, help="cache TTL (gun, hepsi icin override)")
    args = ap.parse_args()

    if args.offline and not any(RAW_DIR.glob("*/*.html")) and not any(RAW_DIR.glob("*.html")):
        print("Cache bos ve --offline secili; once normal calistirin.")
        return 1

    session = requests.Session()
    session.headers.update({"User-Agent": "KKTCMB-Dashboard/1.0 (arastirma kullanimi)"})

    print("1) Liste sayfasi isleniyor (node kesfi)...")
    discovered = discover_nodes(session, args.force, args.offline)
    node_map = merge_maps(discovered, HARDCODED_NODES)

    print(f"2) {sum(len(v) for v in node_map.values())} sayfa isleniyor...")
    records = []
    meta_families = {}
    for (table, kirim), yearmap in sorted(node_map.items()):
        fam_meta = {}
        for year, nodes in sorted(yearmap.items()):
            label = f"{table}/{kirim} {year}"
            parsed = []
            for node in nodes:
                cache = RAW_DIR / table / f"{kirim}__{year}__node{node}.html"
                html, src = cached_fetch(session, f"{BASE}/tr/node/{node}", cache,
                                         ttl_for(year, args.ttl_days), args.force, args.offline)
                if not html:
                    continue
                res, err = parse_page(html)
                if err:
                    warn(f"{label} (node {node}): ayristirma hatasi: {err}")
                    continue
                unit, rows, title = res
                parsed.append({"node": node, "unit": unit, "rows": rows, "title": title})
                time.sleep(0.25)  # siteye nazik davran
            if not parsed:
                warn(f"{label}: hicbir node ayristirilamadi, ATLANDI")
                continue
            best = resolve_duplicates(parsed, label)
            units = {p["unit"] for p in parsed if p["unit"]}
            if len(units) > 1:
                warn(f"{label}: birden fazla birim bulundu: {units}")
            unit = best["unit"] or ("BİN TL" if not units else units.pop())
            if unit and unit.upper() not in ("BİN TL", "BIN TL"):
                warn(f"{label}: beklenmedik birim: {unit!r}")
            for kategori, vals in best["rows"]:
                for ay in range(1, 13):
                    v = vals.get(ay)
                    records.append({
                        "table": table, "kirim": kirim, "yil": year, "ay": ay,
                        "tarih": f"{year:04d}-{ay:02d}-01",
                        "kategori": kategori,
                        "deger": "" if v is None else v,
                        "birim": unit,
                        "node": best["node"],
                    })
            dolu_aylar = sorted({ay for _, vals in best["rows"] for ay, v in vals.items() if v is not None})
            fam_meta[str(year)] = {
                "node": best["node"], "tum_node'lar": nodes, "birim": unit,
                "kategoriler": [k for k, _ in best["rows"]],
                "dolu_aylar": dolu_aylar,
            }
        meta_families[f"{table}|{kirim}"] = fam_meta
        yrs = sorted(int(y) for y in fam_meta)
        if yrs:
            print(f"  {table}/{kirim}: {yrs[0]}-{yrs[-1]} "
                  f"({sum(len(m['kategoriler']) for m in fam_meta.values())} satir-yil)")

    if not records:
        print("HICBIR VERI TOPLANAMADI. Internet baglantinizi / siteyi kontrol edin.")
        return 1

    DATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with DATA_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["table", "kirim", "yil", "ay", "tarih",
                                          "kategori", "deger", "birim", "node"])
        w.writeheader()
        w.writerows(sorted(records, key=lambda r: (r["table"], r["kirim"], r["tarih"], r["kategori"])))

    META_JSON.parent.mkdir(parents=True, exist_ok=True)
    META_JSON.write_text(json.dumps({
        "scrape_zamani": datetime.now().isoformat(timespec="seconds"),
        "kaynak": BASE + LISTING_URLS[0],
        "istatistik": STATS,
        "uyarilar": WARNINGS,
        "aileler": meta_families,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"BITTI: {len(records)} satir -> {DATA_CSV}")
    print(f"       meta      -> {META_JSON}")
    print(f"       ag: {STATS['fetched']} | cache: {STATS['from_cache']} "
          f"| hata: {STATS['failed']} | uyari: {len(WARNINGS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
