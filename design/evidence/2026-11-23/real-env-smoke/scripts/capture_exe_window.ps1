# -*- coding: utf-8 -*-
# 截图当前构建的 EXE 主窗口（只截应用窗口区域，不截整屏）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File capture_exe_window.ps1 -Out <png 路径>
param(
    [string]$Exe = "dist\campus-grab-exe\campus-activity-watch.exe",
    [string]$Out = "design\evidence\2026-11-23\real-env-smoke\exe-demo.png",
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Cap {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
[Win32Cap]::SetProcessDPIAware() | Out-Null

$name = [IO.Path]::GetFileNameWithoutExtension($Exe)
$before = @(Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$proc = Start-Process -FilePath $Exe -ArgumentList "--demo" -PassThru

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$win = $null
while ((Get-Date) -lt $deadline) {
    $cands = @(Get-Process -Name $name -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -notin $before -and $_.MainWindowHandle -ne 0 })
    if ($cands.Count -gt 0) { $win = $cands[0]; break }
    Start-Sleep -Milliseconds 800
}
if ($null -eq $win) { throw "在 $TimeoutSec 秒内没有等到窗口" }

# 等 WebView2 把页面画出来
Start-Sleep -Seconds 10
$win.Refresh()
$handle = $win.MainWindowHandle
[Win32Cap]::SetForegroundWindow($handle) | Out-Null
Start-Sleep -Milliseconds 800

$rect = New-Object Win32Cap+RECT
[Win32Cap]::GetWindowRect($handle, [ref]$rect) | Out-Null
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) { throw "窗口矩形不合法：${width}x${height}" }

$bmp = New-Object System.Drawing.Bitmap $width, $height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)
$dir = Split-Path -Parent $Out
if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$bmp.Save((Resolve-Path -LiteralPath (Split-Path -Parent $Out)).Path + "\" + (Split-Path -Leaf $Out),
    [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()

"title=$($win.MainWindowTitle) pid=$($win.Id) size=${width}x${height} out=$Out"

# demo 实例用完即收；只收本次新起的进程，不碰别人已经开着的实例
Get-Process -Name $name -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -notin $before } | Stop-Process -Force
Wait-Process -Id $proc.Id -Timeout 20 -ErrorAction SilentlyContinue
