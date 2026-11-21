param([string]$Stage='B:\vk-staging\dedup-hud-20261121')
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
try {
 if(Test-Path (Join-Path $Stage 'install.json')){throw 'Installation already recorded; reconcile rather than replay'}
 Add-Type -Path 'B:\Personal\Seamus\Documents\Codex\rainmeter-remote-layout\HudNative.cs'
 [HudNative]::SetProcessDPIAware() | Out-Null
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 $rm=Get-Process Rainmeter | Where-Object SessionId -eq $session | Select-Object -First 1
 if(!$rm){throw 'Existing interactive Rainmeter unavailable'}
 $before=@([HudNative]::Windows($rm.Id)|Where-Object Class -eq 'RainmeterMeterWindow')
 $archive=@($before|Where-Object {$_.Title -like '*\NReconcile\NReconcile.ini' -and $_.Visible})
 if($archive.Count -ne 1){throw 'Exact Archive Queue anchor unavailable'}
 $anchor=$archive[0];$x=$anchor.X;$y=$anchor.Y+$anchor.H+8
 $fits=@([HudNative]::Monitors()|Where-Object {$x -ge $_.x -and $y -ge $_.y -and ($x+420) -le ($_.x+$_.w) -and ($y+218) -le ($_.y+$_.h)}).Count -gt 0
 if(!$fits){throw 'New card would leave the current monitor workarea'}
 $collisions=@($before|Where-Object {$_.Visible -and $x -lt ($_.X+$_.W) -and ($x+420) -gt $_.X -and $y -lt ($_.Y+$_.H) -and ($y+218) -gt $_.Y})
 if($collisions.Count){throw 'New card would overlap an existing HUD'}
 $config=Join-Path $env:APPDATA 'Rainmeter\Rainmeter.ini'
 $root=Split-Path (Split-Path $anchor.Title -Parent) -Parent
 $dest=Join-Path $root 'DedupProgress'
 if(Test-Path $dest){throw 'Destination already exists; reconcile before replacing anything'}
 if((Get-Content $config -Raw) -match '(?m)^\[DedupProgress\]'){throw 'An existing DedupProgress configuration requires reconciliation'}
 $backup='B:\vk-backups\dedup-hud\'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
 New-Item -ItemType Directory -Path $backup | Out-Null
 $preserved=@()
 foreach($path in @($config,$anchor.Title,(Join-Path (Split-Path $anchor.Title -Parent) 'progress.lua'))){
  $copy=Join-Path $backup (Split-Path $path -Leaf)
  Copy-Item -LiteralPath $path -Destination $copy
  $hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $hash){throw 'Backup verification failed'}
  $preserved+=@{source=$path;copy=$copy;sha256=$hash}
 }
 New-Item -ItemType Directory -Path (Join-Path $dest '@Resources') | Out-Null
 [IO.File]::WriteAllText((Join-Path $dest 'DedupProgress.ini'),[IO.File]::ReadAllText((Join-Path $Stage 'DedupProgress.ini')),[Text.Encoding]::Unicode)
 Copy-Item -LiteralPath (Join-Path $Stage 'progress.lua') -Destination (Join-Path $dest '@Resources\progress.lua')
 # Refresh the catalog only if the new skin is not yet known to Rainmeter.
 [HudNative]::Bang('[!ActivateConfig "DedupProgress" "DedupProgress.ini"]')
 Start-Sleep -Milliseconds 700
 $card=@([HudNative]::Windows($rm.Id)|Where-Object Title -eq (Join-Path $dest 'DedupProgress.ini'))
 $catalogRefresh=$false
 if(!$card.Count){
  [HudNative]::Bang('[!RefreshApp]');$catalogRefresh=$true
  Start-Sleep -Milliseconds 900
  [HudNative]::Bang('[!ActivateConfig "DedupProgress" "DedupProgress.ini"]')
  Start-Sleep -Milliseconds 700
 }
 [HudNative]::Bang('[!KeepOnScreen 0 "DedupProgress"][!SetWindowPosition '+$x+' '+$y+' 0 0 "DedupProgress"][!ZPos 0 "DedupProgress"][!ClickThrough 0 "DedupProgress"][!Draggable 1 "DedupProgress"][!SnapEdges 1 "DedupProgress"][!KeepOnScreen 1 "DedupProgress"]')
 [HudNative]::Bang('[!WriteKeyValue "DedupProgress" WindowX '+$x+' "'+$config+'"][!WriteKeyValue "DedupProgress" WindowY '+$y+' "'+$config+'"]')
 Start-Sleep -Milliseconds 700
 $after=@([HudNative]::Windows($rm.Id)|Where-Object Class -eq 'RainmeterMeterWindow')
 $card=@($after|Where-Object Title -eq (Join-Path $dest 'DedupProgress.ini'))
 if($card.Count -ne 1 -or !$card[0].Visible -or $card[0].X -ne $x -or $card[0].Y -ne $y -or $card[0].W -ne 420 -or $card[0].H -ne 218){throw 'New card geometry verification failed'}
 foreach($w in $before){
  $match=@($after|Where-Object Title -eq $w.Title)
  if($match.Count -ne 1){throw 'An existing HUD disappeared'}
  foreach($key in @('X','Y','W','H','Visible')){if($match[0].$key -ne $w.$key){throw ('Existing HUD changed: '+$w.Title+' '+$key)}}
 }
 foreach($p in $preserved|Where-Object source -ne $config){if((Get-FileHash -LiteralPath $p.source).Hash -ne $p.sha256){throw 'Archive Queue source changed'}}
 if((Get-Process -Id $rm.Id).SessionId -ne $session){throw 'Rainmeter process identity changed'}
 @{at=[DateTime]::UtcNow.ToString('o');rainmeterPid=$rm.Id;session=$session;skin=$dest;backup=$backup;preserved=$preserved;card=$card[0];catalogRefresh=$catalogRefresh;existingHudsUnchanged=$true;before=$before;after=$after}|ConvertTo-Json -Depth 7|Set-Content -Encoding UTF8 (Join-Path $Stage 'install.json')
} catch {
 @{error=$_.Exception.Message;at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -Encoding UTF8 (Join-Path $Stage 'install-error.json');exit 1
}
