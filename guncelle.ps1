<#
.SYNOPSIS
    KKTC MB para-banka verisini toplar, dashboard'u uretir ve repoya push eder.

.DESCRIPTION
    MB sunucusu GitHub runner'larinin IP'lerini ag seviyesinde dusurdugu icin
    (TCP 80/443 timeout) veri toplama bu makinede yapilir. Push edilen
    data/kktcmb.csv degisikligi GitHub Actions'ta "Dashboard'u yayinla"
    is akisini tetikler; build + Vercel yayini orada yapilir.

    Zamanlanmis gorev: her ayin 1'i ve 15'i, 10:00.
    Elle calistirma:  .\guncelle.ps1

.PARAMETER Force
    Onbellegi yok say, tum sayfalari yeniden indir.

.PARAMETER NoPush
    Topla ve build et, commit/push yapma (deneme icin).

.PARAMETER Deploy
    Push'a ek olarak yerel Vercel CLI ile de yayinla (Actions'a bagimli kalmamak icin).

.PARAMETER KontrolAtla
    13 gunluk bekleme kuralini yok say, hemen topla (zamanlanmis gorev kullanmaz).

.EXAMPLE
    .\guncelle.ps1
    .\guncelle.ps1 -Force
    .\guncelle.ps1 -NoPush
    .\guncelle.ps1 -KontrolAtla
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$NoPush,
    [switch]$Deploy,
    [switch]$KontrolAtla
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$logDir = Join-Path $PSScriptRoot 'output\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logDosya = Join-Path $logDir ("guncelle-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Yaz {
    param([string]$Mesaj)
    $satir = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Mesaj
    Write-Host $satir
    Add-Content -LiteralPath $logDosya -Value $satir -Encoding utf8
}

function PyCalistir {
    param([string[]]$Arguman)
    & python.exe @Arguman
    if ($LASTEXITCODE -ne 0) { throw ("python {0} basarisiz (cikis={1})" -f ($Arguman -join ' '), $LASTEXITCODE) }
}

function VeriHash {
    $yol = Join-Path $PSScriptRoot 'data\kktcmb.csv'
    if (Test-Path -LiteralPath $yol) { return (Get-FileHash -LiteralPath $yol -Algorithm SHA256).Hash }
    return 'yok'
}

$cikis = 0
try {
    Yaz "=== Guncelleme basladi (Force=$Force, NoPush=$NoPush, Deploy=$Deploy)"

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "python bulunamadi (PATH)" }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git -and -not $NoPush) { throw "git bulunamadi (PATH)" }

    $oncekiHash = VeriHash
    Yaz "Onceki veri parmak izi: $oncekiHash"

    # 0) Bekleme kurali ----------------------------------------------------
    # Gorev her gun calisir; gercek toplama en fazla 13 gunde bir yapilir.
    # Veri degismediyse damga yazilmaz, ertesi gun yeniden denenir.
    $damga = Join-Path $PSScriptRoot 'output\.son_guncelleme'
    if (-not $Force -and -not $KontrolAtla -and (Test-Path -LiteralPath $damga)) {
        $son = (Get-Item -LiteralPath $damga).LastWriteTime
        $gecen = ((Get-Date) - $son).TotalDays
        if ($gecen -lt 13) {
            Yaz ("Son basarili guncelleme {0:yyyy-MM-dd HH:mm} ({1:N1} gun once); 13 gun dolmadi, atlandi." -f $son, $gecen)
            return
        }
    }

    # 1) Veriyi topla ------------------------------------------------------
    Yaz "--- Veri toplaniyor"
    $scrapeArgs = @('scrape.py')
    if ($Force) { $scrapeArgs += '--force' }
    PyCalistir $scrapeArgs

    $yeniHash = VeriHash
    Yaz "Yeni veri parmak izi: $yeniHash"

    if ($yeniHash -eq $oncekiHash -and -not $Force) {
        Yaz "Veri degismedi; build/push atlandi."
        # scrape_meta.json her taramada yeniden yazilir; veri degismediyse
        # calisma agacini kirli birakmamak icin geri al.
        if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git')) {
            & git checkout -- data/scrape_meta.json 2>$null
        }
        return
    }

    # 2) Son veri ayi ------------------------------------------------------
    $ay = (& python.exe -c "import csv;r=[x for x in csv.DictReader(open('data/kktcmb.csv',encoding='utf-8')) if x['deger'].strip()];print(max(x['tarih'] for x in r)[:7])").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ay) { throw "son veri ayi okunamadi" }
    Yaz "Son veri ayi: $ay"

    # 3) Dashboard uret ----------------------------------------------------
    Yaz "--- Dashboard uretiliyor"
    PyCalistir @('build_dashboard.py')

    # 4) Commit + push -----------------------------------------------------
    if ($NoPush) {
        Yaz "NoPush verildi; commit/push atlandi."
    } else {
        Yaz "--- Commit + push"
        & git add data/kktcmb.csv data/scrape_meta.json
        if ($LASTEXITCODE -ne 0) { throw "git add basarisiz" }

        & git diff --cached --quiet
        if ($LASTEXITCODE -eq 0) {
            Yaz "Commit edilecek degisiklik yok."
        } else {
            & git commit -m "veri: $ay"
            if ($LASTEXITCODE -ne 0) { throw "git commit basarisiz" }

            & git push origin HEAD:main
            if ($LASTEXITCODE -ne 0) { throw "git push basarisiz" }
            Yaz "Push tamam; GitHub Actions build + yayini yapacak."
        }
    }

    # 5) Istege bagli yerel yayin -----------------------------------------
    if ($Deploy) {
        Yaz "--- Yerel Vercel yayini"
        & npx --yes vercel@latest deploy site --prod --yes --project kktcmb-dashboard
        if ($LASTEXITCODE -ne 0) { throw "vercel deploy basarisiz" }
        Yaz "Yerel yayin tamam: https://kktcmb-dashboard.vercel.app"
    }

    # 6) Bekleme damgasi ---------------------------------------------------
    # Yalnizca veri gercekten degistiginde yazilir; boylece yeni veri
    # beklenirken ertesi gun yeniden denenir, bulundugunda ise 13 gun susulur.
    if (-not $NoPush) {
        Set-Content -LiteralPath $damga -Value ((Get-Date).ToString('s')) -Encoding utf8
        Yaz ("Bekleme damgasi yazildi: {0} (sonraki toplama en erken {1:yyyy-MM-dd})" -f $damga, (Get-Date).AddDays(13))
    }

    Yaz "=== Guncelleme tamam"
}
catch {
    $cikis = 1
    Yaz ("HATA: " + $_.Exception.Message)
}
finally {
    Yaz "Log: $logDosya"
}

exit $cikis
