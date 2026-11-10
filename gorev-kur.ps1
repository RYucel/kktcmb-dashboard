<#
.SYNOPSIS
    Iki haftalik otomatik guncelleme icin Windows Gorev Zamanlayici gorevini kurar.

.DESCRIPTION
    Her ayin 1'i ve 15'inde 10:00'da guncelle.ps1 calisir; veri degistiyse
    commit + push edilir, GitHub Actions build + Vercel yayinini yapar.

    Gorev "kullanici oturum acmis olmasa da calis" (S4U) modunda kurulur;
    parola sorulmaz. Bilgisayar kapaliysa gorev, acildiginda telafi edilir
    (StartWhenAvailable).

.PARAMETER Kaldir
    Kurulu gorevi siler.

.PARAMETER Saat
    Calisma saati (varsayilan 10:00).

.EXAMPLE
    .\gorev-kur.ps1
    .\gorev-kur.ps1 -Saat 08:30
    .\gorev-kur.ps1 -Kaldir
#>
[CmdletBinding()]
param(
    [switch]$Kaldir,
    [string]$Saat = '10:00'
)

$ErrorActionPreference = 'Stop'
$gorevAdi = 'KKTCMB Dashboard Guncelle'

if ($Kaldir) {
    $var = Get-ScheduledTask -TaskName $gorevAdi -ErrorAction SilentlyContinue
    if (-not $var) { Write-Host "Gorev bulunamadi: $gorevAdi"; exit 0 }
    Unregister-ScheduledTask -TaskName $gorevAdi -Confirm:$false
    Write-Host "Gorev silindi: $gorevAdi"
    exit 0
}

$script = Join-Path $PSScriptRoot 'guncelle.ps1'
if (-not (Test-Path -LiteralPath $script)) { throw "guncelle.ps1 bulunamadi: $script" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $script) `
    -WorkingDirectory $PSScriptRoot

# Ayin 1'i ve 15'i -- cron'un "iki haftada bir" icin pratikteki en yakin karsiligi
$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1, 15 -At $Saat

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$kullanici = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$aciklama = "KKTC MB para-banka verisini toplar ve repoya push eder (ayin 1'i ve 15'i, $Saat)."

$kuruldu = $false
foreach ($logon in @('S4U', 'Interactive')) {
    try {
        $principal = New-ScheduledTaskPrincipal -UserId $kullanici -LogonType $logon -RunLevel Limited
        Register-ScheduledTask -TaskName $gorevAdi -Action $action -Trigger $trigger `
            -Settings $settings -Principal $principal -Description $aciklama -Force | Out-Null
        Write-Host "Gorev kuruldu: $gorevAdi (logon=$logon, gunler=1 ve 15, saat=$Saat, kullanici=$kullanici)"
        $kuruldu = $true
        break
    }
    catch {
        Write-Warning ("logon={0} ile kurulamadi: {1}" -f $logon, $_.Exception.Message)
    }
}

if (-not $kuruldu) { throw "Gorev kurulamadi. Yonetici olarak calistirmayi deneyin." }

$g = Get-ScheduledTask -TaskName $gorevAdi
$g.Triggers | ForEach-Object {
    Write-Host ("  tetikleyici: {0} {1}" -f $_.StartBoundary, ($_.DaysOfMonth -join ','))
}
Write-Host ""
Write-Host "Elle deneme:  Start-ScheduledTask -TaskName '$gorevAdi'"
Write-Host "Loglar:       output\logs\guncelle-*.log"
