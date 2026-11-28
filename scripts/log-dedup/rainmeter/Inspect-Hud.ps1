param([string]$Stage='B:\vk-staging\dedup-hud-20261121',[string]$Receipt='before')
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
try {
 Add-Type -AssemblyName System.Drawing
 if(-not ('HudNative' -as [type])){Add-Type -Path 'B:\Personal\Seamus\Documents\Codex\rainmeter-remote-layout\HudNative.cs'}
 [HudNative]::SetProcessDPIAware() | Out-Null
 Add-Type @'
using System;using System.Runtime.InteropServices;
public class DedupCapture { [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h,IntPtr dc,uint flags); }
'@
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 $rm=Get-Process Rainmeter | Where-Object SessionId -eq $session | Select-Object -First 1
 if(!$rm){throw 'No existing Rainmeter in this interactive session'}
 $windows=@([HudNative]::Windows($rm.Id)|Where-Object Class -eq 'RainmeterMeterWindow')
 $archive=@($windows|Where-Object {$_.Title -like '*\NReconcile\NReconcile.ini' -and $_.Visible})
 if($archive.Count -ne 1){throw 'Exact visible Archive Queue card not found'}
 $anchor=$archive[0];$screens=@([HudNative]::Monitors())
 $proposed=@{x=$anchor.X;y=($anchor.Y+$anchor.H+8);w=420;h=218}
 $fits=@($screens|Where-Object {$proposed.x -ge $_.x -and $proposed.y -ge $_.y -and ($proposed.x+420) -le ($_.x+$_.w) -and ($proposed.y+218) -le ($_.y+$_.h)}).Count -gt 0
 $collisions=@($windows|Where-Object {$_.Visible -and $_.Title -notlike '*\DedupProgress\DedupProgress.ini' -and $proposed.x -lt ($_.X+$_.W) -and ($proposed.x+420) -gt $_.X -and $proposed.y -lt ($_.Y+$_.H) -and ($proposed.y+218) -gt $_.Y})
 $captures=@()
 foreach($w in @($windows|Where-Object {$_.Title -like '*\NReconcile\NReconcile.ini' -or $_.Title -like '*\DedupProgress\DedupProgress.ini'})){
  $label=if($w.Title -like '*\NReconcile\*'){'archive'}else{'dedup'}
  $bmp=[Drawing.Bitmap]::new($w.W,$w.H);$g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc()
  try {$ok=[DedupCapture]::PrintWindow([IntPtr]$w.Handle,$dc,2)}finally{$g.ReleaseHdc($dc);$g.Dispose()}
  $file=Join-Path $Stage ($Receipt+'-'+$label+'.png');$bmp.Save($file,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
  $captures+=@{label=$label;ok=$ok;path=$file}
 }
 @{at=[DateTime]::UtcNow.ToString('o');rainmeterPid=$rm.Id;session=$session;windows=$windows;screens=$screens;proposed=$proposed;fits=$fits;collisions=$collisions;captures=$captures}|ConvertTo-Json -Depth 7|Set-Content -Encoding UTF8 (Join-Path $Stage ($Receipt+'.json'))
} catch { @{error=$_.Exception.Message;at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -Encoding UTF8 (Join-Path $Stage ($Receipt+'-error.json'));exit 1 }
