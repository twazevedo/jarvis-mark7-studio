# Instala tudo que o J.A.R.V.I.S. v5.0 precisa e gera os executaveis .exe (rode UMA vez em cada PC).
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Profile pro    # PC Ryzen 7 5700G + GTX 1660 Super (6 GB VRAM)
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Profile lite   # Notebook i5 (somente CPU)
param([ValidateSet("pro", "lite")][string]$Profile = $(if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "pro" } else { "lite" }))
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "== Configurando J.A.R.V.I.S. Mark VII v5.0 [Perfil: $($Profile.ToUpper())] ==" -ForegroundColor Cyan

function Get-Model($url, $dest) {
    # Baixa para "<arquivo>.part" e so renomeia quando completo (arquivo parcial nunca e tratado como pronto).
    # Se a conexao travar (< 50 KB/s por 45 s), o curl aborta e retoma do ponto onde parou.
    if (Test-Path $dest) { Write-Host "[ok] $(Split-Path $dest -Leaf) ja existe"; return }
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    $part = "$dest.part"
    Write-Host "[baixando] $(Split-Path $dest -Leaf)"
    for ($try = 1; $try -le 8; $try++) {
        & curl.exe -L --fail --connect-timeout 20 --speed-limit 51200 --speed-time 45 `
            --retry 3 --retry-delay 3 -C - -o $part $url
        if ($LASTEXITCODE -eq 0) { Move-Item $part $dest -Force; return }
        Write-Host "[retomando] tentativa $try falhou (codigo $LASTEXITCODE), continuando de onde parou..." -ForegroundColor Yellow
        Start-Sleep 3
    }
    throw "Falha ao baixar $url"
}

# 0) Gerenciador ultra-rapido 'uv' portatil (instala Python 3.12 automaticamente mesmo em PC sem Python!)
$uvExe = ".\tools\uv\uv.exe"
if (-not (Test-Path $uvExe)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $uvExe = (Get-Command uv).Source
    } else {
        New-Item -ItemType Directory -Force -Path ".\tools\uv" | Out-Null
        Get-Model "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" ".\tools\uv.zip"
        Expand-Archive .\tools\uv.zip .\tools\uv -Force
        Remove-Item .\tools\uv.zip -Force
    }
}

function New-Venv($path) {
    if (Test-Path "$path\Scripts\python.exe") { return }
    & $uvExe venv $path --python 3.12 --seed
}

# 1) Ambiente Python do Jarvis + Narrador Neural Offline (Piper + Voz Original Paul Bettany + Edge-TTS)
New-Venv ".\.venv"
$jpy = ".\.venv\Scripts\python.exe"
& $uvExe pip install --python $jpy piper-tts edge-tts mss pyautogui pygetwindow psutil pillow pygame pyperclip
$pv = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium"
Get-Model "$pv/pt_BR-faber-medium.onnx" ".\voices\pt_BR-faber-medium.onnx"
Get-Model "$pv/pt_BR-faber-medium.onnx.json" ".\voices\pt_BR-faber-medium.onnx.json"
$jv = "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high"
Get-Model "$jv/jarvis-high.onnx" ".\voices\jarvis-high.onnx"
Get-Model "$jv/jarvis-high.onnx.json" ".\voices\jarvis-high.onnx.json"
New-Item -ItemType Directory -Force -Path .\assets | Out-Null

# 2) FFmpeg embutido (portatil em tools\ffmpeg\bin com suporte a NVENC)
if (-not (Test-Path ".\tools\ffmpeg\bin\ffmpeg.exe") -and -not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    try {
        Get-Model "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" ".\tools\ffmpeg.zip"
    } catch {
        Get-Model "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" ".\tools\ffmpeg.zip"
    }
    Expand-Archive .\tools\ffmpeg.zip .\tools\ff_tmp -Force
    New-Item -ItemType Directory -Force -Path .\tools\ffmpeg\bin | Out-Null
    Get-ChildItem .\tools\ff_tmp -Recurse -Filter "*.exe" | Copy-Item -Destination .\tools\ffmpeg\bin -Force
    Remove-Item .\tools\ff_tmp -Recurse -Force
    Remove-Item .\tools\ffmpeg.zip -Force
}

# 3) Motores de Imagem e Video conforme o perfil
if ($Profile -eq "pro") {
    if (-not (Test-Path ".\ComfyUI")) { git clone https://github.com/comfyanonymous/ComfyUI.git }
    New-Venv ".\ComfyUI\venv"
    $cpy = ".\ComfyUI\venv\Scripts\python.exe"
    & $uvExe pip install --python $cpy torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
    & $uvExe pip install --python $cpy -r .\ComfyUI\requirements.txt
    $m = ".\ComfyUI\models"
    $hf = "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files"
    Get-Model "https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors" "$m\checkpoints\DreamShaper_8_pruned.safetensors"
    Get-Model "$hf/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors" "$m\diffusion_models\wan2.1_t2v_1.3B_fp16.safetensors"
    Get-Model "$hf/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" "$m\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    Get-Model "$hf/vae/wan_2.1_vae.safetensors" "$m\vae\wan_2.1_vae.safetensors"
    $llms = @("qwen2.5:7b", "qwen2.5-coder:7b", "moondream:latest")
}
else {
    if (-not (Test-Path ".\tools\sd\sd-cli.exe")) {
        New-Item -ItemType Directory -Force -Path .\tools\sd | Out-Null
        Get-Model "https://github.com/leejet/stable-diffusion.cpp/releases/download/master-1015-e41fbcf/sd-master-e41fbcf-bin-win-cpu-x64.zip" ".\tools\sd.zip"
        Expand-Archive .\tools\sd.zip .\tools\sd -Force
        Remove-Item .\tools\sd.zip
    }
    Get-Model "https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors" ".\models\DreamShaper_8_pruned.safetensors"
    Get-Model "https://huggingface.co/latent-consistency/lcm-lora-sdv1-5/resolve/main/pytorch_lora_weights.safetensors" ".\models\lora\lcm-lora-sdv1-5.safetensors"
    $llms = @("qwen2.5:3b")
}

# 4) Ollama (cerebro de linguagem local acelerado pela GTX 1660 Super no Pro)
$ol = if (Get-Command ollama -ErrorAction SilentlyContinue) { (Get-Command ollama).Source } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe") { "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" } else { "" }
if (-not $ol) {
    $ol = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent
    if (-not (Test-Path $ol)) {
        # Plano B: instalador oficial direto do GitHub (instalacao por usuario, sem admin)
        Get-Model "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe" ".\tools\OllamaSetup.exe"
        Start-Process ".\tools\OllamaSetup.exe" -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" -Wait
        Remove-Item ".\tools\OllamaSetup.exe" -Force -ErrorAction SilentlyContinue
    }
}
if (Test-Path $ol) {
    if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
        $env:OLLAMA_FLASH_ATTENTION = "1"
        $env:OLLAMA_MAX_LOADED_MODELS = "1"
        Start-Process $ol -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep 3
    }
    foreach ($l in $llms) { & $ol pull $l }
    foreach ($pair in @(
        @{ name = "jarvis-mark7"; file = ".\models\Modelfile.mark7" },
        @{ name = "jarvis-coder"; file = ".\models\Modelfile.coder" },
        @{ name = "jarvis-cinema"; file = ".\models\Modelfile.cinema" }
    )) {
        if (Test-Path $pair.file) {
            if ($Profile -eq "lite") {
                $tmpMf = "$($pair.file).lite.tmp"
                $raw = [System.IO.File]::ReadAllText((Resolve-Path $pair.file))
                $raw = $raw -replace "FROM qwen2\.5(?:-coder)?:7b", "FROM qwen2.5:3b" -replace "PARAMETER num_thread 12", "PARAMETER num_thread 6" -replace "PARAMETER num_ctx 16384", "PARAMETER num_ctx 8192"
                [System.IO.File]::WriteAllText($tmpMf, $raw, [System.Text.UTF8Encoding]::new($false))
                & $ol create $pair.name -f $tmpMf
                Remove-Item $tmpMf -Force -ErrorAction SilentlyContinue
            } else {
                & $ol create $pair.name -f $pair.file
            }
        }
    }
}

# 5) Compila os executaveis nativos (.exe)
$csc = Get-ChildItem "$env:WINDIR\Microsoft.NET\Framework64\v4*\csc.exe" | Select-Object -First 1 -ExpandProperty FullName
if ($csc -and (Test-Path ".\tools\Launcher.cs")) {
    & $csc /nologo /target:winexe /out:".\Jarvis.exe" ".\tools\Launcher.cs"
    & $csc /nologo /target:winexe /define:FORCE_LITE /out:".\Jarvis-Lite.exe" ".\tools\Launcher.cs"
    & $csc /nologo /target:winexe /define:FORCE_PRO /out:".\Jarvis-Pro.exe" ".\tools\Launcher.cs"
}

Write-Host "`nTudo pronto! Clique duas vezes em Jarvis-$($Profile.Substring(0,1).ToUpper() + $Profile.Substring(1)).exe para iniciar." -ForegroundColor Green
