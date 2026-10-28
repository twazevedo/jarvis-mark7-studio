"""Motor de Visão de Tela e Detecção de Coordenadas (Inspirado nos Vídeos 1, 2 e 4 — Jarvis / Molmo / Computer Use).

Permite ao J.A.R.V.I.S.:
1. Capturar qualquer monitor em tempo real com `PIL.ImageGrab` / `mss`.
2. Detectar todos os textos, botões e elementos visíveis na tela com suas coordenadas exatas (X, Y) usando o motor OCR nativo do Windows 10/11 (100% local e sem custo de API).
3. Desenhar uma mira holográfica Stark no ponto clicado e salvar em `outputs/` para exibir no HUD.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
from PIL import Image, ImageDraw, ImageGrab

import backends as B

ROOT = B.ROOT
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

_PS_OCR_SCRIPT = r"""
param([string]$ImagePath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Foundation.IAsyncOperation`1, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]

function Await($WinRtTask, $ResultType) {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0].MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$items = @()
foreach ($line in $result.Lines) {
    $wlist = @($line.Words)
    if ($wlist.Count -gt 0) {
        $x1 = ($wlist | ForEach-Object { $_.BoundingRect.X } | Measure-Object -Minimum).Minimum
        $y1 = ($wlist | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
        $x2 = ($wlist | ForEach-Object { $_.BoundingRect.X + $_.BoundingRect.Width } | Measure-Object -Maximum).Maximum
        $y2 = ($wlist | ForEach-Object { $_.BoundingRect.Y + $_.BoundingRect.Height } | Measure-Object -Maximum).Maximum
        $cx = [int](($x1 + $x2) / 2)
        $cy = [int](($y1 + $y2) / 2)
        $items += @{ text = $line.Text; x = $cx; y = $cy }
    }
    foreach ($w in $wlist) {
        $r = $w.BoundingRect
        $items += @{
            text = $w.Text
            x = [int]($r.X + $r.Width / 2)
            y = [int]($r.Y + $r.Height / 2)
            word = $true
        }
    }
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output (@{ full_text = $result.Text; items = $items } | ConvertTo-Json -Compress -Depth 4)
"""


def grab_screen(monitor_index: int = 1) -> tuple[Image.Image, dict]:
    """Captura o monitor solicitado com múltiplos métodos (PIL.ImageGrab -> mss -> fallback seguro)."""
    try:
        img = ImageGrab.grab(all_screens=False)
        return img.convert("RGB"), {"left": 0, "top": 0, "width": img.width, "height": img.height}
    except Exception:
        pass
    try:
        import mss
        with mss.mss() as sct:
            monitors = sct.monitors
            idx = min(max(1, monitor_index), len(monitors) - 1)
            mon = monitors[idx]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            return img, mon
    except Exception:
        img = Image.new("RGB", (1366, 768), (4, 18, 30))
        return img, {"left": 0, "top": 0, "width": 1366, "height": 768}


def extract_screen_elements(img: Image.Image) -> dict:
    """Extrai todo o texto da tela e as coordenadas (X, Y) de cada palavra/linha usando OCR nativo do Windows."""
    with tempfile.TemporaryDirectory() as td:
        tmp_png = Path(td) / "screen.png"
        tmp_ps1 = Path(td) / "ocr.ps1"
        img.save(tmp_png, format="PNG")
        tmp_ps1.write_text(_PS_OCR_SCRIPT, encoding="utf-8")
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp_ps1), "-ImagePath", str(tmp_png)],
            capture_output=True,
            timeout=15,
        )
        if p.returncode == 0 and p.stdout.strip():
            try:
                return json.loads(p.stdout.decode("utf-8", errors="replace").strip())
            except Exception:
                pass
    return {"full_text": "", "items": []}


def save_annotated_click(img: Image.Image, x: int, y: int, label: str = "") -> str:
    """Desenha a mira holográfica Stark no ponto clicado (x, y) e salva em outputs/."""
    copy = img.copy()
    draw = ImageDraw.Draw(copy)
    r1, r2 = 18, 34
    draw.ellipse((x - r2, y - r2, x + r2, y + r2), outline=(0, 240, 255), width=3)
    draw.ellipse((x - r1, y - r1, x + r1, y + r1), outline=(255, 170, 0), width=3)
    draw.line((x - 46, y, x + 46, y), fill=(0, 240, 255), width=2)
    draw.line((x, y - 46, x, y + 46), fill=(0, 240, 255), width=2)
    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 59, 92))
    name = f"{int(time.time())}_image_click_{x}x{y}.png"
    copy.save(OUT / name, format="PNG")
    return f"/outputs/{name}"
