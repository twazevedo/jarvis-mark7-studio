# J.A.R.V.I.S. Mark VII (v4.5) — Stark Holographic AI Studio & Computer-Use Agent

Sistema **100% local, gratuito e sem restrições** inspirado no **J.A.R.V.I.S.** do Homem de Ferro, unindo:
1. **3 Módulos Neurais Especialistas no Ollama** (`jarvis-mark7` Geral, `jarvis-coder` Engenharia Sênior, `jarvis-cinema` Roteiros & Documentários).
2. **CodeMind AI Studio Integrado (Estilo Claude Artifacts)**: Pipeline Multi-Agente de 3 estágios (*1. Arquiteto `<arquitetura>` + 2. Dev Sênior + 3. Auditor QA `<auditoria>`*), 6 áreas poliglotas, editor em tempo real, **Preview ao Vivo** (`iframe`) e botão **💾 Salvar Projeto no PC (`workspace/`)**.
3. **Visão Computacional da Tela & Controle de Mouse/Teclado (Série 6 Vídeos Inteligência Mil Grau)**:
   - `tasks_folder/handle_image.py` + `screen_vision.py`: Enxerga sua tela em tempo real via OCR/Visão nativa do Windows.
   - `tasks_folder/handle_click.py`: Localiza coordenadas `(X, Y)` de qualquer botão/texto na tela, clica automaticamente e desenha a mira Stark onde clicou.
   - `tasks_folder/automatic_text_typing.py`: Digitação automática onde o cursor estiver.
   - `tasks_folder/nova_tarefa.py` + `task_manager.py`: Agente que programa e instala novas tarefas Python em `tasks_folder/` em tempo real!
   - `tasks_folder/snake_game.py`: Jogo da Cobrinha Stark Edition em Pygame.
4. **Voz Humana Natural de Estúdio + Ativação por 2 Palmas (👏👏) e Voz Contínua ("Jarvis...")** (`voice.py`).
5. **Estúdio Visual Completo**:
   - Imagens 8K, Vídeos Curtos e **Documentários Longos de 10 a 20+ minutos** (roteiro por capítulos + narração neural + imagens + movimento de câmera FFmpeg + legenda `.srt`).

---

## 💻 Perfis de Hardware (`Jarvis-Pro.exe` & `Jarvis-Lite.exe`)

| Recurso | **Jarvis-Pro.exe** (Ryzen 7 5700G + GTX 1660 Super 6 GB, 16 GB RAM) | **Jarvis-Lite.exe** (Notebook i5-12450H, 8 GB RAM, só CPU) |
|---|---|---|
| **Executável 1-clique** | `Jarvis-Pro.exe` (ou `Jarvis.exe`) | `Jarvis-Lite.exe` (ou `Jarvis.exe`) |
| **Cérebro IA** | `jarvis-mark7` / `dolphin3:8b` / `qwen2.5:7b` na GPU | `jarvis-mark7` / `jarvis-coder` (`qwen2.5:3b`) na CPU |
| **Geração de Imagens** | ComfyUI + DreamShaper 8 na GPU (~15–30 s) | `stable-diffusion.cpp` + DreamShaper 8 + LCM 4 passos na CPU (~65 s) |
| **Vídeos Curtos** | **Wan 2.1 1.3B** generativo na GPU | Quadro cinematográfico + câmera FFmpeg (6 s, 720p) |
| **Documentários (10–20m)** | Roteiro + Voz Neural + Cenas GPU + FFmpeg (`.mp4` + `.srt`) | Roteiro + Voz Neural + Cenas CPU + FFmpeg (`.mp4` + `.srt`) |

---

## 🚀 Como baixar e rodar no seu outro PC (Ryzen 7 5700G + GTX 1660 Super)

No seu outro computador, abra o **PowerShell** e rode:

```powershell
git clone https://github.com/twazevedo/jarvis-mark7-studio.git
cd jarvis-mark7-studio
.\Jarvis-Pro.exe
```

> Na primeira execução, o **`Jarvis-Pro.exe`** detectará automaticamente que é a primeira vez naquele PC e oferecerá instalar todos os modelos, vozes (`jarvis-high.onnx` original do Paul Bettany + `pt_BR-faber-medium.onnx`), FFmpeg, Ollama e ComfyUI (ou você pode rodar direto `powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Profile pro`).
