# Liga o J.A.R.V.I.S. e abre o navegador.
#   .\start.ps1 -Profile pro    # ComfyUI + Ollama + Jarvis (GPU NVIDIA)
#   .\start.ps1 -Profile lite   # Ollama + Jarvis (so CPU)
param([ValidateSet("pro", "lite")][string]$Profile = $(if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "pro" } else { "lite" }))
Set-Location $PSScriptRoot
$env:JARVIS_PROFILE = $Profile

if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
}

if ($Profile -eq "pro") {
    # --lowvram: essencial para 6 GB de VRAM. Se der imagem preta/NaN, adicione --force-fp32 ou --fp32-vae
    Start-Process ".\ComfyUI\venv\Scripts\python.exe" -ArgumentList "main.py --lowvram --listen 127.0.0.1 --port 8188" `
        -WorkingDirectory ".\ComfyUI" -WindowStyle Minimized
}

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8766"
& ".\.venv\Scripts\python.exe" .\server.py
