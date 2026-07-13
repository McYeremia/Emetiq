# Daftarkan pipeline harian Big Money ke Windows Task Scheduler.
#
#   powershell -ExecutionPolicy Bypass -File scripts\register_bigmoney_task.ps1
#
# Kenapa di mesin lokal dan bukan di cloud: IDX membalas HTTP 403 ke IP datacenter
# (runner GitHub Actions dan Hugging Face Spaces sama-sama ditolak), sementara IP
# rumah lolos.
#
# Tugasnya berjalan sebagai pengguna yang sedang login — tanpa menyimpan password,
# jadi tak perlu hak admin. Konsekuensinya: PC harus dalam keadaan login. Kalau jam
# 17:30 laptop sedang mati, StartWhenAvailable membuat tugasnya menyusul begitu PC
# nyala, jadi harinya tidak bolong.
#
# Hapus lagi dengan:  Unregister-ScheduledTask -TaskName "EMETIQ Big Money Harian"

$ErrorActionPreference = "Stop"

$taskName = "EMETIQ Big Money Harian"
$script   = Join-Path $PSScriptRoot "bigmoney_daily_task.cmd"

if (-not (Test-Path $script)) { throw "Tidak ketemu: $script" }

$action = New-ScheduledTaskAction -Execute $script

# 17:30 WIB: pasar tutup 16:00, data EOD IDX sudah terbit. Senin-Jumat; akhir pekan
# tak perlu dikecualikan secara khusus karena IDX membalas nol baris dan pipeline
# berhenti tenang, tapi menjadwalkannya saja lebih jujur.
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 17:30

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Ingest IDX + skor Big Money + laporan harian. Jalan dari IP lokal karena IDX menolak IP datacenter." `
    -Force | Out-Null

Write-Host "Terdaftar: $taskName"
Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime, LastRunTime, LastTaskResult | Format-List
