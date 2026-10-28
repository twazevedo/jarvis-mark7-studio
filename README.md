# J.A.R.V.I.S. Mark VII (v5.0 Pro) — Stark Holographic AI Studio & Computer-Use Agent

Sistema **100% local, gratuito e sem restrições** inspirado no **J.A.R.V.I.S.** do Homem de Ferro, calibrado sob medida para **AMD Ryzen 7 5700G (8C/16T) + NVIDIA GeForce GTX 1660 SUPER (6 GB VRAM) + 16 GB RAM**:

1. **3 Módulos Neurais Especialistas 7B Acelerados por GPU no Ollama**:
   - `jarvis-mark7` (`qwen2.5:7b` GPU + 16K contexto): Inteligência Geral Stark.
   - `jarvis-coder` (`qwen2.5-coder:7b` GPU + 16K contexto): Engenharia de Software Sênior & CodeMind Studio.
   - `jarvis-cinema` (`qwen2.5:7b` GPU + 16K contexto): Diretor de Roteiros & Documentários Full HD.
2. **CodeMind AI Studio Integrado (Estilo Claude Artifacts)**: Pipeline Multi-Agente de 3 estágios (*1. Arquiteto `<arquitetura>` + 2. Dev Sênior + 3. Auditor QA `<auditoria>`*), 6 áreas poliglotas, editor em tempo real, **Preview ao Vivo** (`iframe`) e botão **💾 Salvar Projeto no PC (`workspace/`)**.
3. **Visão Computacional Híbrida (GPU Multimodal `moondream` + OCR Nativo Windows) & Controle Autônomo**:
   - `tasks_folder/handle_image.py` + `screen_vision.py`: Enxerga sua tela em tempo real combinando Visão Multimodal na GPU + OCR nativo do Windows.
   - `tasks_folder/handle_click.py`: Localiza coordenadas `(X, Y)` de qualquer botão/texto na tela, clica automaticamente e desenha a mira Stark onde clicou.
   - `tasks_folder/automatic_text_typing.py`: Digitação automática onde o cursor estiver.
   - `tasks_folder/nova_tarefa.py` + `task_manager.py`: Agente que programa e instala novas tarefas Python em `tasks_folder/` em tempo real!
   - `tasks_folder/gpu_booster.py`: Monitora a GTX 1660 Super (Carga, Temperatura °C, Potência W, VRAM) e libera VRAM/RAM instantaneamente.
   - `tasks_folder/snake_game.py`: Jogo da Cobrinha Stark Edition em Pygame.
4. **Telemetria Quádrupla em Tempo Real no HUD**:
   - Monitora **CPU Ryzen 7 5700G (16T)**, **RAM Neural (16 GB)**, **GPU GTX 1660 Super (% + °C)** e **VRAM Dedicada (6 GB GDDR6)**.
5. **Voz Humana Natural de Estúdio + Ativação por 2 Palmas (👏👏) e Voz Contínua ("Jarvis...")** (`voice.py`).
6. **Estúdio Visual Completo com Smart VRAM Guard (6 GB) & Aceleração NVENC Full HD**:
   - Descarrega automaticamente o LLM da VRAM antes de renderizar no ComfyUI (`--lowvram --fp32-vae`) e libera a VRAM após a criação.
   - Documentários Longos de 10 a 20+ minutos em **Full HD 1080p (30 FPS)** renderizados em paralelo via **NVIDIA NVENC (`h264_nvenc`)** + Ryzen 7 5700G.

---

## 💻 Perfis de Hardware (`Jarvis-Pro.exe` & `Jarvis-Lite.exe`)

| Recurso | **Jarvis-Pro.exe** (Ryzen 7 5700G 8C/16T + GTX 1660 Super 6 GB, 16 GB RAM) | **Jarvis-Lite.exe** (Notebook i5-12450H, 8 GB RAM, só CPU) |
|---|---|---|
| **Executável 1-clique** | `Jarvis-Pro.exe` (ou `Jarvis.exe`) | `Jarvis-Lite.exe` (ou `Jarvis.exe`) |
| **Cérebro IA** | `jarvis-mark7` (`qwen2.5:7b`) + `jarvis-coder` (`qwen2.5-coder:7b`) + `moondream` na GPU | `jarvis-mark7` / `jarvis-coder` (`qwen2.5:3b`) na CPU |
| **Geração de Imagens** | ComfyUI (`--lowvram --fp32-vae`) + DreamShaper 8 na GPU (~12–20 s) | `stable-diffusion.cpp` + DreamShaper 8 + LCM 4 passos na CPU (~65 s) |
| **Vídeos Curtos** | **Wan 2.1 1.3B** generativo na GPU | Quadro cinematográfico + câmera FFmpeg (6 s, 720p) |
| **Documentários (10–20m)** | **Full HD 1080p @ 30fps** + **NVIDIA NVENC** + Voz Neural + `.srt` | HD 720p @ 25fps + Voz Neural + Cenas CPU + `.srt` |

---

## 🚀 Como rodar no seu PC (Ryzen 7 5700G + GTX 1660 Super)

Abra o **PowerShell** na pasta do projeto e rode:

```powershell
.\Jarvis-Pro.exe
```

*(Ou execute `powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Profile pro` para instalar/atualizar todos os modelos).*
