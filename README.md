# KKTC MB — Para-Banka Zaman Serileri Dashboard

KKTC Merkez Bankası'nın [Para Banka Verileri](https://mb.gov.ct.tr/tr/veriler/istatistikiveriler/para-banka-eski)
sayfalarından **Mevduat** ve **Krediler** istatistiklerini toplayıp, tek dosyalık
çevrimdışı çalışabilir bir zaman serisi dashboard'u üretir.

## Dosyalar

| Dosya | İşlev |
|---|---|
| `scrape.py` | MB sitesinden verileri toplar → `data/kktcmb.csv` (+ `data/scrape_meta.json`) |
| `build_dashboard.py` | CSV verisinden dashboard üretir → `output/kktcmb_dashboard.html` |
| `guncelle.ps1` | Topla + build + commit + push (Görev Zamanlayıcı'nın çalıştırdığı script) |
| `gorev-kur.ps1` | İki haftalık Windows Görev Zamanlayıcı görevini kurar / kaldırır |
| `template.html` | Dashboard'un HTML/CSS/JS şablonu (PlaceHolder'lı) |
| `.github/workflows/update.yml` | Commit'lenmiş CSV'den dashboard üretip Vercel'e yayınlar |
| `assets/fonts/` | Wix Madefor woff2 alt kümeleri (build sırasında base64 gömülür) |
| `site/index.html` | Dashboard'un yayına hazır kopyası (build otomatik üretir) |
| `data/raw/` | İndirilen ham sayfalar (cache) |
| `data/kktcmb.csv` | Tidy veri: `table, kirim, yil, ay, tarih, kategori, deger, birim, node` |
| `output/kktcmb_dashboard.html` | **Tek dosya dashboard** — çift tıklayıp tarayıcıda açın |

## Kullanım

```powershell
.\guncelle.ps1                # topla + build + commit + push (tam akış)
python scrape.py              # sadece veri topla / güncelle (cache'li)
python build_dashboard.py     # sadece dashboard'u yeniden üret
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

### Otomatik güncelleme (iki haftada bir)

Toplama ile yayın **iki ayrı yerde** çalışır. Sebebi ölçülmüş bir kısıt:
MB sunucusu (`mb.gov.ct.tr` → 185.64.80.30) yurt dışı/veri merkezi IP'lerini ağ
seviyesinde düşürüyor — DNS çözülüyor ama TCP 80/443 timeout, ping yok.
Bu yüzden Actions (veya Vercel/Cloudflare gibi bulut) içinden `scrape.py`
çalıştırılamaz; toplama KKTC/TR IP'sinden yapılmalı.

| Adım | Nerede | Ne yapar |
|---|---|---|
| 1. Toplama | Kendi makineniz — Görev Zamanlayıcı → `guncelle.ps1` | `scrape.py` + `build_dashboard.py`; veri değiştiyse `data/` commit + push |
| 2. Yayın | GitHub Actions → `.github/workflows/update.yml` | Commit'lenmiş CSV'den dashboard'u üretir, Vercel'e yayınlar |

**Kurulum (bir kez):**

```powershell
.\gorev-kur.ps1              # her gün 10:00'da kontrol
.\gorev-kur.ps1 -Saat 08:30  # farklı saat
.\gorev-kur.ps1 -Kaldir      # görevi sil
```

Görev **her gün** çalışır ama gerçek toplama 13 günde bir yapılır: script
`output/.son_guncelleme` damgasına bakar. Veri değişmediyse damga yazılmaz ve
ertesi gün yeniden denenir; böylece yeni veri yayınlandığı ilk gün yakalanır.
Veri değiştiğinde damga yazılır ve 13 gün susulur.

Bu tasarım "PC o gün kapalıydı" sorununu çözer: `StartWhenAvailable` sayesinde
kaçırılan çalışma makine açılınca telafi edilir, damga dolmadığı için ertesi gün
de yeniden denenir. `RunOnlyIfNetworkAvailable` açıktır, süre limiti 3 saattir.

Çalışma modu:

- **Yönetici olarak** çalıştırırsanız görev `S4U` ile kurulur → oturum açık
  olmasa da çalışır.
- **Normal kullanıcı** olarak çalıştırırsanız `InteractiveToken` ile kurulur →
  yalnızca oturum açıkken çalışır (yönetici hakkı istemez).

**Elle çalıştırma:**

```powershell
.\guncelle.ps1               # topla + build + commit + push
.\guncelle.ps1 -KontrolAtla  # 13 günlük beklemeyi yok say, hemen topla
.\guncelle.ps1 -Force        # önbelleği yok say, her sayfayı yeniden indir
.\guncelle.ps1 -NoPush       # sadece topla + build (deneme)
.\guncelle.ps1 -Deploy       # push'a ek olarak yerel Vercel yayını da yap
```

Davranış:

- `data/kktcmb.csv` parmak izi (sha256) değişmediyse build ve push atlanır,
  `data/scrape_meta.json` geri alınır (çalışma ağacı temiz kalır).
- Değişiklik varsa `data/kktcmb.csv` + `data/scrape_meta.json` commit edilir
  (veri geçmişi) ve `main`'e push edilir → Actions yayını tetiklenir.
- `site/` ve `output/` `.gitignore` içindedir; 5 MB'lık HTML repoya girmez.
- Loglar: `output/logs/guncelle-YYYYMMDD-HHmmss.log`.
- Actions'ta başarısız koşu olursa GitHub e-posta bildirimi gönderir; yerel
  yayın için `-Deploy` kullanılabilir.


**Actions secret'ları** (Settings → Secrets and variables → Actions):

| Secret | Nereden |
|---|---|
| `VERCEL_TOKEN` | `vercel tokens create <ad>` (hesap geneli) |
| `VERCEL_ORG_ID` | `vercel link` sonrası `.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | aynı dosya → `projectId` |

> **Not:** `.github/workflows/erisim-testi.yml` yalnızca elle çalışan bir tanı
> aracıdır (kontrol siteleri + DNS + TCP 80/443 + MB URL'leri). Erişim engeli
> kalkarsa toplama tekrar Actions'a taşınabilir.

**Görev doğrulaması**

```powershell
Start-ScheduledTask -TaskName 'KKTCMB Dashboard Guncelle'
Get-ScheduledTaskInfo -TaskName 'KKTCMB Dashboard Guncelle'   # LastTaskResult = 0
```

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

Python 3.10+ ve şu paketler:

```bash
pip install -r requirements.txt
```

`requests`, `beautifulsoup4`, `lxml`, `pandas`, `plotly` (son ikisi yalnızca
`build_dashboard.py` için; `plotly` paketi dashboard'a gömülecek
`plotly.min.js` dosyasını sağlar).
