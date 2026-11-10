<#
.SYNOPSIS
    Iki haftalik otomatik guncelleme icin Windows Gorev Zamanlayici gorevini kurar.

.DESCRIPTION
    Her gun 10:00'da guncelle.ps1 calisir. Script 13 gunluk bekleme kuralini
    kendi uygular: veri degistiyse damga yazar ve 13 gun susar, degismediyse
    ertesi gun yeniden dener. Boylece bilgisayar planlanan gunde kapali olsa
    bile acildigi ilk gun guncelleme kendiliginden yapilir.

    Commit + push sonrasi GitHub Actions build + Vercel yayinini yapar.

    Bilgisayar kapaliyken kacirilan calisma, makine acilinca telafi edilir
    (StartWhenAvailable).

.PARAMETER Kaldir
    Kurulu gorevi siler.

.PARAMETER Saat
    Gunluk kontrol saati (varsayilan 10:00).

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

$arguman = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $script
$kullanici = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$baslangic = (Get-Date).ToString('yyyy-MM-dd') + 'T' + $Saat + ':00'
$aciklama = "KKTC MB para-banka verisini her gun kontrol eder, 13 gunde bir toplar ve repoya push eder (kontrol saati: $Saat)."
# Gorev ortaminda PATH farkli olabildigi icin tam yol kullanilir (0x80070002 onlemi).
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

# XML ile kurulum: PowerShell 5.1'in New-ScheduledTaskTrigger'i aylik tetikleyiciyi
# desteklemez. Gunluk tetikleyici + StartWhenAvailable ile kacirilan gun telafi edilir;
# gercek toplama sikligini guncelle.ps1'in 13 gunluk bekleme kurali belirler.
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$aciklama</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$baslangic</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$kullanici</UserId>
      <LogonType>S4U</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowHardTerminate>true</AllowHardTerminate>
    <ExecutionTimeLimit>PT3H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$powershell</Command>
      <Arguments>$arguman</Arguments>
      <WorkingDirectory>$PSScriptRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

try {
    Register-ScheduledTask -TaskName $gorevAdi -Xml $xml -Force | Out-Null
    Write-Host "Gorev kuruldu (S4U: oturum acik olmasa da calisir)."
}
catch {
    # S4U yonetici hakki ister; yonetici degilsek "oturum acikken calis" moduna dus.
    Write-Warning ("S4U ile kurulamadi: " + $_.Exception.Message)
    $xml = $xml -replace '<LogonType>S4U</LogonType>', '<LogonType>InteractiveToken</LogonType>'
    Register-ScheduledTask -TaskName $gorevAdi -Xml $xml -Force | Out-Null
    Write-Host "Gorev kuruldu (oturum acikken calisir modu)."
    Write-Host "  Not: bilgisayar kapali/oturum kapaliyken calismasi icin bu scripti"
    Write-Host "       yonetici olarak bir kez calistirin (S4U moduna gecer)."
}

$g = Get-ScheduledTask -TaskName $gorevAdi
Write-Host ("  durum: {0} | kullanici: {1} | logon: {2}" -f $g.State, $g.Principal.UserId, $g.Principal.LogonType)
$g.Triggers | ForEach-Object {
    $gun = if ($_.DaysInterval) { "her $($_.DaysInterval) gun" } else { ($_.DaysOfMonth -join ',') }
    Write-Host ("  tetikleyici: {0} | {1}" -f $_.StartBoundary, $gun)
}
Write-Host ""
Write-Host "Elle deneme:  Start-ScheduledTask -TaskName '$gorevAdi'"
Write-Host "Loglar:       output\logs\guncelle-*.log"
