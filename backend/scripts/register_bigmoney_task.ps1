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

# 19:00 WIB, bukan 17:30. Kita tak pernah membuktikan IDX sudah menerbitkan data EOD
# pada 17:30 — yang terverifikasi cuma: pukul 20:00 datanya ada. Kalau IDX belum terbit,
# ia membalas 200 dengan NOL BARIS, dan pipeline menganggapnya hari non-bursa lalu
# berhenti tenang tanpa alarm. Kegagalan yang diam seperti itu justru yang paling mahal,
# jadi ambil marjin: laporannya toh dibaca malam hari.
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 19:00

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
