param([string]$Stage='B:\vk-staging\dedup-hud-20261121')
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
try {
 Add-Type -Path 'B:\Personal\Seamus\Documents\Codex\rainmeter-remote-layout\HudNative.cs'
 [HudNative]::Bang('[!Refresh "DedupProgress"]');Start-Sleep -Seconds 16
 [HudNative]::Bang('[!CommandMeasure MeasureUI "dofile([[B:\vk-staging\dedup-hud-20261121\Test-Hud.lua]])" "DedupProgress"]')
 & (Join-Path $Stage 'Inspect-Hud.ps1') -Stage $Stage -Receipt 'after'
 $receipt=Join-Path $env:APPDATA 'JaxCore\InstalledComponents\DedupProgress\@Resources\display-state.txt'
 Copy-Item $receipt (Join-Path $Stage 'live-first.txt')
 $test=Get-Content (Join-Path $Stage 'lua-tests.txt') -Raw
 if(!$test.StartsWith('PASS:')){throw ('Rainmeter Lua tests failed: '+$test)}
 $config=Join-Path $env:APPDATA 'Rainmeter\Rainmeter.ini'
 Copy-Item $config (Join-Path $Stage 'Rainmeter.after.ini')
 Get-Process Rainmeter | Select-Object Id,SessionId | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Stage 'live-process.json')
} catch { @{error=$_.Exception.Message;at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -Encoding UTF8 (Join-Path $Stage 'verify-error.json');exit 1 }
