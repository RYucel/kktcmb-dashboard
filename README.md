# KKTC MB — Para-Banka Zaman Serileri Dashboard

KKTC Merkez Bankası'nın [Para Banka Verileri](https://mb.gov.ct.tr/tr/veriler/istatistikiveriler/para-banka-eski)
sayfalarından **Mevduat** ve **Krediler** istatistiklerini toplayıp, tek dosyalık
çevrimdışı çalışabilir bir zaman serisi dashboard'u üretir.

## Dosyalar

| Dosya | İşlev |
|---|---|
| `scrape.py` | MB sitesinden verileri toplar → `data/kktcmb.csv` (+ `data/scrape_meta.json`) |
| `build_dashboard.py` | CSV verisinden dashboard üretir → `output/kktcmb_dashboard.html` |
| `template.html` | Dashboard'un HTML/CSS/JS şablonu (PlaceHolder'lı) |
| `assets/fonts/` | Wix Madefor woff2 alt kümeleri (build sırasında base64 gömülür) |
| `site/index.html` | Dashboard'un yayına hazır kopyası (build otomatik üretir) |
| `data/raw/` | İndirilen ham sayfalar (cache) |
| `data/kktcmb.csv` | Tidy veri: `table, kirim, yil, ay, tarih, kategori, deger, birim, node` |
| `output/kktcmb_dashboard.html` | **Tek dosya dashboard** — çift tıklayıp tarayıcıda açın |

## Kullanım

```bash
python scrape.py              # verileri topla / güncelle (cache'li)
python build_dashboard.py     # dashboard'u yeniden üret
```

Çıktı `output/kktcmb_dashboard.html` tek bir dosyadır; Plotly.js, veri ve
arayüz yazı tipleri (Wix Madefor Display/Text, base64 woff2) içine gömülüdür.
İnternetsiz, herhangi bir tarayıcıda açılır.

## Arayüz

Tasarım, [Hallmark](https://github.com/nutlope/hallmark) tasarım sisteminin
**Dusk** temasıyla ve *app screen* kapsamıyla kurulmuştur. Öne çıkanlar:

- Koyu slate zemin, tek cam (glass) üst bar; periwinkle + apricot sinyal renkleri
- KPI'lar kart değil, tek bir **ruled tally** bandı (6 sütun, 1px ayraçlar)
- Sol tarafta sticky **bölüm rayı** (Krediler, Mevduat, Kamu ve özel, Karşılaştırma),
  scroll ile aktif nokta
- Kontroller kutulu segment değil: **ruled list + periwinkle nokta**; seçenekler
  ghost pill + nokta (chip)
- Tüm renkler `:root` token'larından, grafik paleti Dusk'tan türetilmiş 14 renk
- Seçili tarih aralığı URL'e yazılır: `?from=2018-03&to=2021-06`

## Yayına alma (Vercel — bedava)

Site yayında: **https://kktcmb-dashboard.vercel.app**

`build_dashboard.py` her çalışmada `site/index.html` kopyası da üretir.
Yayınlamak / güncellemek için:

```bash
# ilk kurulum (bir kez): vercel login  +  vercel project create kktcmb-dashboard
python scrape.py && python build_dashboard.py
vercel deploy site --prod --yes --project kktcmb-dashboard
```

Proje: `ryucels-projects/kktcmb-dashboard` (Vercel Hobby/bedava plan).
Yalnızca `site/` klasörü yüklenir; scraper kodu ve ham veri depoya girmez.
Alternatif bedava servisler de aynı klasörle çalışır (Netlify Drop, GitHub Pages,
Cloudflare Pages — hepsi `site/index.html` statik dosyasını servis eder).

### Otomatik güncelleme (GitHub Actions)

`.github/workflows/update.yml` veriyi **ayın 1'i ve 15'inde** (06:00 UTC) toplar,
değişiklik varsa dashboard'u üretip Vercel'e yayınlar. Cron "iki haftada bir"
ifadesini desteklemediği için 1 + 15 kullanılır; bu pratikte 14-16 gün aralık verir.

Depoya eklenmesi gereken secret'lar (Settings → Secrets and variables → Actions):

| Secret | Nereden |
|---|---|
| `VERCEL_TOKEN` | vercel.com/account/tokens |
| `VERCEL_ORG_ID` | `vercel link` sonrası `.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | aynı dosya → `projectId` |

Davranış:

- `data/kktcmb.csv` parmak izi (sha256) değişmediyse build ve deploy atlanır;
  yeni ay veya revizyon varsa yayınlanır.
- `data/kktcmb.csv` ve `data/scrape_meta.json` commit edilir. Bu hem veri geçmişi
  bırakır hem de GitHub'ın "60 gün hareketsizlikte zamanlanmış işi kapatma"
  kuralını engeller.
- `site/` ve `output/` `.gitignore` içindedir; 5 MB'lık HTML repoya girmez,
  Vercel'e CLI ile yüklenir.
- İlk çalıştırmayı Actions sekmesinden **Run workflow** ile elle tetikleyin.
  MB sitesi GitHub runner IP'lerini engellerse `scrape.py` hata verir; o durumda
  iş kendi makinenizde veya TR'deki bir VPS'te çalıştırılmalıdır.
- Başarısız koşularda GitHub e-posta bildirimi gönderir.

### scrape.py seçenekleri

```bash
python scrape.py --force        # cache'i yok say, her sayfayı yeniden indir
python scrape.py --offline      # ağ isteği yapma, sadece cache kullan
python scrape.py --ttl-days 3   # cache yenileme süresini (gün) override et
```

Cache davranışı: içinde bulunulan yılın sayfaları her gün, önceki yıl 30 günde
bir, daha eski yıllar yılda bir yenilenir. MB siteye yeni ay verisi ekledikçe
`python scrape.py && python build_dashboard.py` çalıştırmak yeterlidir.

## Dashboard içeriği

- **KPI kartları**: Toplam Krediler, Toplam Mevduat, Kredi/Mevduat oranı,
  YP kredi ve YP mevduat payları, Tüketici+Kredi Kartı payı (aylık/yıllık değişimlerle)
- **Krediler (sektörlere göre)**: 14 sektör — yığın alan / pay % / çizgi modları,
  Toplam–TL(TP)–Döviz(YP) kırılımı, log ölçek
- **Mevduat**: türe ve vadeye göre dağılım (aynı modlar), bankalar hariç/dahil ana seriler
- **Krediler — Kamu/Özel** ayrımı
- **Kredi ↔ Mevduat**: karşılaştırma, loan-to-deposit oranı, YoY % büyüme
- Global tarih aralığı filtresi (2010-01 – son veri ayı)

## Veri notları

- **Kaynak birimi**: BİN TL; dashboard milyar TL gösterir.
- **Kapsam**: 2010-01 – 2026-09 (MB yeni ay yayınladıkça uzar).
- **2014 mevduat tanım değişikliği**: 2010–2013 tablolarında "TOPLAM"
  bankalararası mevduatı içerir; 2014'ten itibaren "TOPLAM" bankalar hariçtir ve
  "GENEL TOPLAM" ayrı yayınlanır. Dashboard, 2010–2013 için *TOPLAM − Bankalar*
  hesaplayarak **tutarlı "Mevduat (bankalar hariç)"** serisi kurar.
- **Vade dağılımı (2010–2013)**: kaynak tablo yapısı gereği bankalararası
  mevduat vade kalemlerinin içindedir; dashboard'da ilgili notla belirtilmiştir.
- **Revizyon uyarısı**: MB verileri geçici mali tablolara dayandırır; sonraki
  dönemlerde revize edilebilir.
- Aynı yıl için birden fazla node yayınlandığında (ör. 2026 mevduat-vade)
  scraper **en dolu olanı** seçer ve çelişkileri `scrape_meta.json`'a loglar.

### Yeni yıl eklenmesi (ör. 2027)

MB 2027 sayfalarını açtığında `scrape.py` bunları **liste sayfasından otomatik
keşfeder** — tek yapmanız gereken tekrar çalıştırmaktır. Keşif başarısız olursa
`scrape.py` içindeki `HARDCODED_NODES` haritasına yeni node numaralarını
(elde etmek için: liste sayfasındaki yıl linklerinin `/tr/node/XXXX` adresleri)
ekleyebilirsiniz.

## Gereksinimler

Python 3.10+ ve şu paketler: `requests`, `beautifulsoup4`, `lxml`, `pandas`, `plotly`
(son ikisi yalnızca `build_dashboard.py` için; `plotly` paketi dashboard'a gömülecek
`plotly.min.js` dosyasını sağlar).
