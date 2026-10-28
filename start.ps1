# Liga o J.A.R.V.I.S. v5.0 e abre o navegador.
#   .\start.ps1 -Profile pro    # ComfyUI (--lowvram --fp32-vae) + Ollama GPU + Jarvis (Ryzen 7 5700G + GTX 1660 Super)
#   .\start.ps1 -Profile lite   # Ollama + Jarvis (so CPU)
param([ValidateSet("pro", "lite")][string]$Profile = $(if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "pro" } else { "lite" }))
Set-Location $PSScriptRoot
$env:JARVIS_PROFILE = $Profile
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"

if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
}

if ($Profile -eq "pro" -and (Test-Path ".\ComfyUI\venv\Scripts\python.exe")) {
    # --lowvram --fp32-vae: calibrado para GTX 1660 Super (6 GB VRAM Turing), evitando NaN/imagem preta
    Start-Process ".\ComfyUI\venv\Scripts\python.exe" -ArgumentList "main.py --lowvram --fp32-vae --listen 127.0.0.1 --port 8188" `
        -WorkingDirectory ".\ComfyUI" -WindowStyle Minimized
}

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8766"
& ".\.venv\Scripts\python.exe" .\server.py
