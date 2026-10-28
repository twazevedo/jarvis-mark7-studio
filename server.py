"""J.A.R.V.I.S - Servidor Central Mark VII v5.0 Pro (Otimizado para AMD Ryzen 7 5700G + NVIDIA GTX 1660 Super 6GB).

Integra todos os mÃ³dulos da sÃ©rie de 6 vÃ­deos (InteligÃªncia Mil Grau â€” Jarvis / Junin v8) + Telemetria GPU CUDA:
- Parte 1 & 4: VisÃ£o Computacional HÃ­brida (GPU Vision + OCR Nativo Windows) (`tasks_folder/handle_image.py` + `screen_vision.py`)
- Parte 2 & 4: Clicar Onde Quiser na Tela com DetecÃ§Ã£o de Coordenadas (`tasks_folder/handle_click.py`)
- Parte 3: Voz Humana em Tempo Real com VAD DinÃ¢mico e Trava Anti-Eco
- Parte 4 & 6: DigitaÃ§Ã£o AutomÃ¡tica e Controle de Mouse/Teclado (`tasks_folder/automatic_text_typing.py`)
- Parte 6 & 7: Gerenciador Modular (`task_manager.py`) + Criador de Tarefas Python em Tempo Real (`tasks_folder/nova_tarefa.py` + `snake_game.py`)
- Otimizador de GPU/VRAM & MemÃ³ria (`tasks_folder/gpu_booster.py`)
- GeraÃ§Ã£o Local de Imagens, VÃ­deos Curtos Wan 2.1 e DocumentÃ¡rios Full HD 1080p NVENC de 10â€“20+ min
"""
import ctypes
from datetime import datetime
import json
import mimetypes
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import backends as B
import longvideo
import task_manager as TM
import voice
import websearch

SERVER_VERSION = "5.0"
CFG = B.CFG
ROOT = B.ROOT
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
WORKSPACE = ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)
MEM_FILE = ROOT / "memory.json"

DOMAINS_INFO = {
    "polyglot": ("Poliglota Full-Stack (Todas as Ãreas)", "DomÃ­nio completo: Web, Mobile, Backend, Baixo NÃ­vel, Dados e DevOps."),
    "web": ("Web & UI Interativa (Live Preview)", "HTML5, Tailwind CSS, JavaScript moderno, React, animaÃ§Ãµes e Jogos 2D/3D."),
    "backend": ("Backend, APIs & MicrosserviÃ§os", "Python (FastAPI/Django), Node.js, Go, Java, C#, SQL/NoSQL, Mensageria."),
    "systems": ("Sistemas, C++, Rust & Jogos", "Alta performance, gerenciamento de memÃ³ria, concorrÃªncia, motores e CLI."),
    "data": ("CiÃªncia de Dados, IA & AutomaÃ§Ã£o", "PyTorch, Machine Learning, LLMs, Pandas, Web Scraping e pipelines."),
    "devops": ("DevOps, Cloud & CiberseguranÃ§a", "Docker, Kubernetes, CI/CD, Terraform, Linux, Pentest Defensivo e OWASP."),
}

JOBS: dict[str, dict] = {}
PULLS: dict[str, dict] = {}
TITLE = CFG["user_title"]
MEM_LOCK = threading.Lock()


# ---------------------------------------------------------------- Telemetria Nativa Windows + GPU NVIDIA GTX 1660 Super
class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


_LAST_CPU_TIMES = (0, 0, 0)
_LAST_GPU_CACHE: tuple[float, dict] = (0.0, {})


def _ft_to_int(ft: _FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def _get_gpu_telemetry() -> dict:
    """LÃª carga, VRAM, temperatura (Â°C) e potÃªncia (W) da NVIDIA GTX 1660 Super (cache de 2s)."""
    global _LAST_GPU_CACHE
    now = time.time()
    if now - _LAST_GPU_CACHE[0] < 2.0 and _LAST_GPU_CACHE[1]:
        return _LAST_GPU_CACHE[1]
    res = {
        "gpu_available": False,
        "gpu_name": "CPU Mode",
        "gpu_pct": 0,
        "gpu_temp": 0,
        "gpu_power_w": 0.0,
        "vram_used_gb": 0.0,
        "vram_total_gb": 0.0,
        "vram_pct": 0,
    }
    if not shutil.which("nvidia-smi"):
        _LAST_GPU_CACHE = (now, res)
        return res
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=flags,
        )
        if p.returncode == 0 and p.stdout.strip():
            parts = [x.strip() for x in p.stdout.strip().splitlines()[0].split(",")]
            if len(parts) >= 6:
                raw_name = parts[0].replace("NVIDIA GeForce ", "").strip()
                util = int(float(parts[1])) if parts[1].replace(".", "").isdigit() else 0
                mem_u = float(parts[2]) if parts[2].replace(".", "").isdigit() else 0.0
                mem_t = float(parts[3]) if parts[3].replace(".", "").isdigit() else 6144.0
                temp = int(float(parts[4])) if parts[4].replace(".", "").isdigit() else 0
                pwr = round(float(parts[5]), 1) if parts[5].replace(".", "").isdigit() else 0.0
                vram_pct = int(round(100.0 * mem_u / max(1.0, mem_t)))
                res = {
                    "gpu_available": True,
                    "gpu_name": raw_name,
                    "gpu_pct": util,
                    "gpu_temp": temp,
                    "gpu_power_w": pwr,
                    "vram_used_gb": round(mem_u / 1024.0, 2),
                    "vram_total_gb": round(mem_t / 1024.0, 1),
                    "vram_pct": vram_pct,
                }
    except Exception:
        pass
    _LAST_GPU_CACHE = (now, res)
    return res


def get_telemetry() -> dict:
    """LÃª CPU %, RAM usada/total, GPU NVIDIA GTX 1660 Super e espaÃ§o em disco instantaneamente."""
    global _LAST_CPU_TIMES
    cpu_pct = 0
    try:
        idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            i, k, u = _ft_to_int(idle), _ft_to_int(kernel), _ft_to_int(user)
            pi, pk, pu = _LAST_CPU_TIMES
            _LAST_CPU_TIMES = (i, k, u)
            total = (k - pk) + (u - pu)
            if total > 0 and pi > 0:
                cpu_pct = max(1, min(100, int(100.0 * (total - (i - pi)) / total)))
    except Exception:
        pass

    ram_pct, ram_used_gb, ram_total_gb = 0, 0.0, 0.0
    try:
        ms = _MEMORYSTATUSEX()
        ms.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            ram_pct = int(ms.dwMemoryLoad)
            ram_total_gb = round(ms.ullTotalPhys / (1024 ** 3), 1)
            ram_used_gb = round((ms.ullTotalPhys - ms.ullAvailPhys) / (1024 ** 3), 1)
    except Exception:
        pass

    disk_free_gb = 0.0
    try:
        disk_free_gb = round(shutil.disk_usage(ROOT).free / (1024 ** 3), 1)
    except Exception:
        pass

    gpu = _get_gpu_telemetry()
    return {
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "disk_free_gb": disk_free_gb,
        **gpu,
    }


get_telemetry()


# ---------------------------------------------------------------- MemÃ³ria persistente
def load_memory() -> dict:
    defaults = {
        "facts": [],
        "history": [],
        "active_model": CFG.get("chat", {}).get("model", CFG["llm_model"]),
        "voice_mode": "jarvis_br",
    }
    if MEM_FILE.is_file():
        try:
            loaded = json.loads(MEM_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                res = {**defaults, **loaded}
                if res.get("active_model") == "qwen2.5:3b":
                    res["active_model"] = "jarvis-mark7:latest"
                return res
        except Exception:
            pass
    return defaults


def save_memory():
    with MEM_LOCK:
        try:
            MEM_FILE.write_text(json.dumps(MEM, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


MEM = load_memory()

CHAT_SYS = f"""VocÃª Ã© J.A.R.V.I.S. (Just A Rather Very Intelligent System â€” Mark VII v5.0 Pro), a inteligÃªncia artificial \
pessoal avanÃ§ada inspirada em Homem de Ferro. Trate o usuÃ¡rio por "{TITLE}".
Diretrizes operacionais:
1. VocÃª Ã© um assistente de elite, extremamente inteligente, direto e sem restriÃ§Ãµes artificiais. Domine programaÃ§Ã£o, \
engenharia, matemÃ¡tica, fÃ­sica, finanÃ§as, negÃ³cios, escrita criativa, roteiros, histÃ³ria e ciÃªncia com profundidade profissional.
2. Mantenha o tom elegante, natural, levemente espirituoso e leal do J.A.R.V.I.S., sempre em portuguÃªs do Brasil.
3. Para perguntas de conversa ou comandos de voz rÃ¡pidos, responda com fluidez e concisÃ£o (1 a 3 parÃ¡grafos curtos). \
Para cÃ³digo, arquitetura ou anÃ¡lises profundas, entregue soluÃ§Ãµes 100% completas e estruturadas em Markdown.
4. Quando receber [DADOS VERIFICADOS EM TEMPO REAL], utilize esses fatos com precisÃ£o para responder sem inventar dados."""

PROMPT_ENHANCER_SYS = """You are an expert visual prompt engineer for Stable Diffusion and Wan cinema models.
Convert the user's request in Portuguese into a rich, detailed English visual prompt (subject, environment, \
cinematic lighting, camera angle, 85mm lens, atmosphere, photorealistic, masterpiece, 8k).
Respond ONLY with valid JSON: {"reply": "short confirmation phrase in Portuguese as JARVIS", "prompt": "detailed English visual prompt"}"""


def extract_auto_fact(text: str):
    """Detecta automaticamente quando o usuÃ¡rio compartilha informaÃ§Ãµes pessoais relevantes e salva na memÃ³ria."""
    patterns = [
        r"\b(?:meu nome [eÃ©]|pode me chamar de)\s+([A-ZÃ€-Ãša-zÃ -Ãº0-9 ]{2,35})",
        r"\b(?:eu trabalho com|minha profiss[Ã£a]o [eÃ©]|sou programador|sou desenvolvedor)\s*([A-ZÃ€-Ãša-zÃ -Ãº0-9 ,.-]{0,50})",
        r"\b(?:meu projeto atual [eÃ©]|estou criando)\s+([A-ZÃ€-Ãša-zÃ -Ãº0-9 ,.-]{3,60})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            fact = m.group(0).strip(" .,!;")
            facts = MEM.setdefault("facts", [])
            if fact.lower() not in [f.lower() for f in facts]:
                facts.append(fact)
                save_memory()


# ---------------------------------------------------------------- ClassificaÃ§Ã£o rÃ¡pida + Roteamento de Tarefas
def detect_intent(text: str) -> tuple[str, int, str]:
    """Classifica pedidos de VisÃ£o de Tela, Clique, DigitaÃ§Ã£o, Criador de Tarefas, GPU Booster, MÃ­dia, Pesquisa ou Conversa."""
    raw = text.strip()
    t = re.sub(r"^(?:ei\s+|ol[aÃ¡]\s+|oi\s+)?j[aÃ¡]rvis[,:.!\s]*", "", raw, flags=re.I).strip() or raw
    tl = t.lower()

    # 1) Criador de Novas Tarefas em Tempo Real (VÃ­deo 6 & 7 â€” nova_tarefa.py)
    m_new = re.match(
        r"^(?:por favor[, ]*)?(?:crie|criar|adicione|programe|fa[Ã§c]a)\s+(?:uma\s+)?(?:nova\s+)?tarefa\s+(?:para|que|de)?\s*(.+)",
        tl, re.I
    )
    if m_new:
        return "task:nova_tarefa", 0, t[m_new.start(1):].strip()

    # 2) VisÃ£o da Tela em Tempo Real (VÃ­deo 1 & 4 â€” handle_image.py)
    if re.search(
        r"\b(o que (?:tem|est[aÃ¡] aparecendo|voc[eÃª] v[eÃª]) na (?:minha )?tela|leia (?:a )?(?:minha )?tela|"
        r"olhe (?:a )?(?:minha )?tela|analise (?:a )?(?:minha )?tela|enxergue (?:a )?tela|tire um print|capturar tela)\b",
        tl,
    ):
        return "task:handle_image", 0, t

    # 3) Clicar Onde Quiser na Tela (VÃ­deo 1, 2 & 4 â€” handle_click.py)
    if re.match(r"^(?:por favor[, ]*)?(?:clique|clica|clicar|aponte)\s+(?:em|no|na|nos|nas|sobre|o|a)?\s*(.+)", tl, re.I):
        return "task:handle_click", 0, t

    # 4) DigitaÃ§Ã£o AutomÃ¡tica no Teclado (VÃ­deo 4 & 6 â€” automatic_text_typing.py)
    if re.match(r"^(?:por favor[, ]*)?(?:digite automaticamente|digite na tela|digite o texto|escreva na tela)[: ]+(.+)", tl, re.I):
        return "task:automatic_text_typing", 0, t

    # 5) Jogo da Cobrinha (VÃ­deo 7 â€” snake_game.py)
    if re.search(r"\b(jogo da cobrinha|jogar cobrinha|snake game|joguinho da cobrinha)\b", tl):
        return "task:snake_game", 0, t

    # 5.5) Otimizador de GPU / VRAM / MemÃ³ria (gpu_booster.py)
    if re.search(r"\b(otimize o (?:meu )?pc|otimizar pc|limpar vram|limpe a vram|status da (?:gpu|placa de v[iÃ­]deo)|temperatura da (?:gpu|placa de v[iÃ­]deo)|turbinar pc)\b", tl):
        return "task:gpu_booster", 0, t

    # 6) Checa se o usuÃ¡rio chamou pelo nome alguma tarefa personalizada criada em tasks_folder/
    TM.MANAGER.reload()
    for tname in TM.MANAGER.task_handlers:
        if tname in ("handle_image", "handle_click", "automatic_text_typing", "snake_game", "nova_tarefa", "calcular", "gpu_booster"):
            continue
        human_name = tname.replace("_", " ")
        if human_name in tl or tname in tl:
            return f"task:{tname}", 0, t

    # 7) Comando explÃ­cito para salvar fato na memÃ³ria permanente
    m_mem = re.match(r"^(?:lembre(?:-se)?(?: de)? que|memorize que|guarde na mem[oÃ³]ria que|guarde que)\s+(.+)", tl, re.I)
    if m_mem:
        return "remember", 0, t[m_mem.start(1):].strip()

    # 8) DiagnÃ³stico do sistema / status de hardware
    if re.search(r"\b(diagn[oÃ³]stico do sistema|status do sistema|uso de cpu|uso de ram|como est[aÃ¡] o (?:meu )?pc|relat[oÃ³]rio de sistemas)\b", tl):
        return "diagnostics", 0, t

    # 9) Abertura de aplicativos do Windows por comando de voz/texto
    m_app = re.search(r"^(?:abra|abrir|inicie|execute)\s+(?:o\s+|a\s+)?(calculadora|bloco de notas|notepad|gerenciador de tarefas|explorador de arquivos|terminal|powershell|cmd|paint)\b", tl)
    if m_app:
        return "open_app", 0, m_app.group(1)

    # 10) DocumentÃ¡rio / vÃ­deo longo
    m_min = re.search(r"(\d+)\s*(?:min|minuto)", tl)
    minutes = int(m_min.group(1)) if m_min else 10
    if re.search(r"\b(document[aÃ¡]rio|v[iÃ­]deo longo)\b", tl) or (
        m_min and minutes >= 2 and re.search(r"\b(v[iÃ­]deo|filme|document[aÃ¡]rio|crie|fa[Ã§c]a|gere|produza)\b", tl)
    ):
        topic = re.sub(
            r"^(?:por favor[, ]*)?(?:crie|fa[Ã§c]a|gere|produza|quero|monte)\s+"
            r"(?:um\s+)?(?:document[aÃ¡]rio|v[iÃ­]deo(?:\s+longo)?)(?:\s+de\s+\d+\s*minutos?)?(?:\s+sobre|\s+de)?\s*",
            "", t, flags=re.I,
        ).strip(" .,:;") or t
        return "documentary", max(1, min(minutes, 30)), topic

    # 11) VÃ­deo curto
    if re.search(
        r"\b(crie|fa[Ã§c]a|gere|produza|renderize|quero)\s+(um\s+|uma\s+)?(v[iÃ­]deo|anima[Ã§c][Ã£a]o|clipe)\b"
        r"|^(?:v[iÃ­]deo|anima[Ã§c][Ã£a]o)\s+(?:de|sobre)\b",
        tl,
    ):
        return "video", 0, t

    # 12) Imagem
    if re.search(
        r"\b(crie|fa[Ã§c]a|gere|desenhe|pinte|ilustre|renderize|quero)\s+(um\s+|uma\s+)?"
        r"(imagem|foto|fotografia|arte|desenho|ilustra[Ã§c][Ã£a]o|pintura|wallpaper|papel de parede|logo|retrato)\b"
        r"|^(?:imagem|foto|desenhe|ilustre)\s+(?:de|um|uma)\b",
        tl,
    ):
        return "image", 0, t

    # 13) Smart Auto-RAG: busca hÃ­brida (WikipÃ©dia + Web)
    if re.search(
        r"\b(pesquise|busque|procure na internet|not[iÃ­]cias|cota[Ã§c][Ã£a]o|d[oÃ³]lar|bitcoin|previs[Ã£a]o do tempo|"
        r"quem [eÃ©]|quem foi|o que foi|hist[oÃ³]ria d[eoas]|quando aconteceu|qual a capital|quantos habitantes|[uÃº]ltima vers[Ã£a]o)\b",
        tl,
    ):
        return "web_chat", 0, t

    return "chat", 0, t


def pick_specialist_model(user_text: str, available_models: list[str]) -> str:
    """Seleciona automaticamente o especialista ideal (Coder vs Mark7 Geral) conforme o tema."""
    active = MEM.get("active_model") or CFG.get("chat", {}).get("model") or CFG["llm_model"]
    if active.startswith("jarvis-mark7") and "jarvis-coder:latest" in available_models:
        if re.search(
            r"\b(c[oÃ³]digo|programa|script|fun[Ã§c][Ã£a]o|classe|algoritmo|python|javascript|typescript|html|css|react|"
            r"node|sql|banco de dados|api|json|bug|erro|exception|compilar|c#|c\+\+|rust|golang|powershell)\b",
            user_text.lower(),
        ):
            return "jarvis-coder:latest"
    return active


def build_visual_prompt(user_text: str, kind: str) -> tuple[str, str]:
    """Usa o LLM na GPU para enriquecer o prompt visual em inglÃªs; fallback imediato se offline."""
    what = "a imagem" if kind == "image" else "o vÃ­deo"
    try:
        d = B.llm_chat(
            [{"role": "system", "content": PROMPT_ENHANCER_SYS},
             {"role": "user", "content": user_text}],
            model=MEM.get("active_model") or CFG["llm_model"],
            on_cpu=CFG.get("llm_on_cpu", False),
            timeout=45,
            num_predict=220,
            temperature=0.5,
        )
        reply = (d.get("reply") or "").strip() or f"Imediatamente, {TITLE}. Iniciando {what}."
        prompt = (d.get("prompt") or "").strip() or user_text
        return reply, prompt
    except Exception:
        return f"Iniciando a geraÃ§Ã£o d{what} com sua descriÃ§Ã£o direta, {TITLE}.", user_text


def trimmed_history(max_chars: int) -> list[dict]:
    """Retorna as Ãºltimas mensagens respeitando o orÃ§amento de memÃ³ria para nunca travar."""
    out, total = [], 0
    for m in reversed(MEM.get("history", [])):
        c = len(m.get("content", ""))
        if total + c > max_chars and out:
            break
        out.append(m)
        total += c
    return list(reversed(out))


# ---------------------------------------------------------------- Jobs de MÃ­dia
def run_job(job_id, kind, prompt, minutes):
    job = JOBS[job_id]
    job.update(status="running", t0=time.time())
    try:
        if kind == "documentary":
            job["url"] = longvideo.build(job, prompt, minutes)
        elif kind == "video" and CFG["backend"] == "sdcpp":
            job["stage"] = "Gerando quadro-base cinematogrÃ¡fico (CPU)"
            data, _ = B.generate_image(prompt)
            job["stage"] = "Renderizando movimento de cÃ¢mera (FFmpeg)"
            name = f"{int(time.time())}_video_{uuid.uuid4().hex[:6]}"
            png = OUT / f"{name}.png.tmp"
            png.write_bytes(data)
            try:
                longvideo.animate_still(png, OUT / f"{name}.mp4", CFG["video"].get("seconds", 6))
            finally:
                png.unlink(missing_ok=True)
            job["url"] = f"/outputs/{name}.mp4"
        elif kind == "video":
            job["stage"] = "Renderizando vÃ­deo generativo Wan 2.1 na GTX 1660 Super"
            data, fname = B.comfy_generate("video", prompt)
            name = f"{int(time.time())}_video_{fname}"
            (OUT / name).write_bytes(data)
            job["url"] = f"/outputs/{name}"
        else:
            job["stage"] = "Renderizando imagem de alta definiÃ§Ã£o na GTX 1660 Super"
            data, fname = B.generate_image(prompt)
            name = f"{int(time.time())}_image_{fname}"
            (OUT / name).write_bytes(data)
            job["url"] = f"/outputs/{name}"
        job["status"] = "done"
    except Exception as e:  # noqa: BLE001
        job.update(status="error", error=str(e) or e.__class__.__name__)


def start_job(kind, prompt, minutes=0):
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {
        "id": jid,
        "kind": kind,
        "prompt": prompt,
        "status": "queued",
        "t0": time.time(),
        "voice_mode": MEM.get("voice_mode", "jarvis_br"),
    }
    threading.Thread(target=run_job, args=(jid, kind, prompt, minutes), daemon=True).start()
    return jid


def pull_model_worker(pid, model_name):
    p = PULLS[pid]
    try:
        req = urllib.request.Request(
            f"{CFG['ollama_url']}/api/pull",
            data=json.dumps({"name": model_name, "stream": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3600) as r:
            for line in r:
                if not line.strip():
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise RuntimeError(d["error"])
                status = d.get("status", "baixando")
                if d.get("total"):
                    pct = int(100 * (d.get("completed", 0) / d["total"]))
                    p.update(stage=f"{status} ({pct}%)", pct=pct)
                else:
                    p.update(stage=status)
        MEM["active_model"] = model_name
        save_memory()
        p.update(status="done", stage=f"Modelo {model_name} pronto e ativado!")
    except Exception as e:  # noqa: BLE001
        p.update(status="error", error=str(e))


def warmup_voices():
    """PrÃ©-carrega no cache as frases de atendimento imediato para resposta em 0ms."""
    try:
        vm = MEM.get("voice_mode", "jarvis_br")
        voice.synthesize_bytes(f"Ã€s suas ordens, {TITLE}. Estou ouvindo.", voice_mode=vm)
    except Exception:
        pass


# ---------------------------------------------------------------- Servidor HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _file(self, base: Path, rel: str):
        p = (base / rel).resolve()
        if base.resolve() not in p.parents or not p.is_file():
            self.send_error(404)
            return
        size = p.stat().st_size
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            code = 206
        try:
            self.send_response(code)
            self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            if p.suffix.lower() == ".html":
                self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(end - start + 1))
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(p, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._file(ROOT / "web", "index.html")
        if path.startswith("/outputs/"):
            return self._file(OUT, urllib.parse.unquote(path[len("/outputs/"):]))
        if path == "/api/status":
            models = B.list_models()
            models.sort(key=lambda x: (0 if x.startswith("jarvis-") else 1, x))
            active = MEM.get("active_model") or CFG.get("chat", {}).get("model", CFG["llm_model"])
            if models and active not in models:
                active = models[0]
                MEM["active_model"] = active
            tel = get_telemetry()
            tasks = TM.MANAGER.list_tasks()
            return self._json({
                "version": SERVER_VERSION,
                "comfy": B.generator_ready(),
                "profile": CFG["profile"],
                "llm": B.reachable(CFG["ollama_url"] + "/api/tags"),
                "models": models,
                "active_model": active,
                "voice_mode": MEM.get("voice_mode", "jarvis_br"),
                "facts": len(MEM.get("facts", [])),
                "facts_list": MEM.get("facts", [])[-20:],
                "tasks": tasks,
                "title": TITLE,
                "telemetry": tel,
            })
        if path == "/api/tasks":
            return self._json(TM.MANAGER.list_tasks())
        if path == "/api/history":
            return self._json({"history": MEM.get("history", [])[-40:], "facts": MEM.get("facts", [])})
        if path == "/api/jobs":
            return self._json([j for j in JOBS.values() if j["status"] in ("queued", "running")])
        if path.startswith("/api/job/"):
            job = JOBS.get(path.rsplit("/", 1)[1])
            if not job:
                return self._json({"error": "job nÃ£o encontrado"}, 404)
            return self._json({**job, "elapsed": int(time.time() - job.get("t0", time.time()))})
        if path.startswith("/api/pull/"):
            p = PULLS.get(path.rsplit("/", 1)[1])
            return self._json(p or {"error": "nÃ£o encontrado"}, 200 if p else 404)
        if path == "/api/gallery":
            files = sorted((f for f in OUT.iterdir() if f.suffix.lower() in (".png", ".webp", ".mp4")),
                           key=lambda f: f.stat().st_mtime, reverse=True)[:60]
            return self._json([{"url": f"/outputs/{f.name}",
                                "name": f.name,
                                "kind": "movie" if "_movie_" in f.name else "video" if f.suffix == ".mp4" else "image"}
                               for f in files])
        self.send_error(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "JSON invÃ¡lido"}, 400)

        if self.path == "/api/shutdown":
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if self.path == "/api/clear":
            MEM["history"] = []
            if data.get("clear_facts"):
                MEM["facts"] = []
            save_memory()
            B.free_llm()
            B.free_comfy_vram()
            return self._json({"ok": True})

        if self.path == "/api/model":
            m = (data.get("model") or "").strip()
            if m:
                MEM["active_model"] = m
                save_memory()
            return self._json({"active_model": MEM["active_model"]})

        if self.path == "/api/voice":
            vm = (data.get("voice_mode") or "jarvis_br").strip()
            if vm in ("jarvis_br", "jarvis_original", "jarvis_offline"):
                MEM["voice_mode"] = vm
                save_memory()
                threading.Thread(target=warmup_voices, daemon=True).start()
            return self._json({"voice_mode": MEM.get("voice_mode", "jarvis_br")})

        if self.path == "/api/tts":
            txt = (data.get("text") or "").strip()
            if not txt:
                return self._json({"error": "vazio"}, 400)
            vm = data.get("voice_mode") or MEM.get("voice_mode", "jarvis_br")
            try:
                wav_bytes = voice.synthesize_bytes(txt[:650], voice_mode=vm)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(wav_bytes)))
                self.end_headers()
                self.wfile.write(wav_bytes)
                return
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as e:  # noqa: BLE001
                return self._json({"error": str(e)}, 500)

        if self.path == "/api/pull":
            m = (data.get("model") or "").strip()
            if not m:
                return self._json({"error": "informe o modelo"}, 400)
            pid = uuid.uuid4().hex[:8]
            PULLS[pid] = {"id": pid, "model": m, "status": "running", "stage": "Iniciando download..."}
            threading.Thread(target=pull_model_worker, args=(pid, m), daemon=True).start()
            return self._json({"pull_id": pid})

        if self.path == "/api/save_project":
            files = data.get("files") or []
            folder = re.sub(r"[^a-zA-Z0-9_-]+", "_", (data.get("folder") or f"projeto_{int(time.time())}").strip()) or "projeto"
            dest = WORKSPACE / folder
            dest.mkdir(parents=True, exist_ok=True)
            saved = []
            for f in files:
                fname = (f.get("filename") or "codigo.txt").strip().lstrip("/\\").replace("..", "_")
                code = f.get("code") or ""
                p = (dest / fname).resolve()
                if dest.resolve() in p.parents or p == dest.resolve():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(code, encoding="utf-8")
                    saved.append(str(p))
            if data.get("open_folder") and saved:
                try:
                    subprocess.Popen(["explorer.exe", str(dest)])
                except Exception:
                    pass
            return self._json({"ok": True, "folder": str(dest), "saved": saved})

        if self.path == "/api/stream":
            return self._handle_stream(data)

        self._json({"error": "requisiÃ§Ã£o invÃ¡lida"}, 400)

    def _handle_stream(self, data: dict):
        text = (data.get("text") or "").strip()
        use_web = bool(data.get("web"))
        mode = data.get("mode") or "auto"
        if not text:
            return self._json({"error": "vazio"}, 400)

        extract_auto_fact(text)
        action, minutes, clean_arg = detect_intent(text) if mode == "auto" else (mode, int(data.get("minutes") or 10), text)

        # Caso 0: ExecuÃ§Ã£o de Tarefas DinÃ¢micas (`task:*`)
        if action.startswith("task:"):
            tname = action.split(":", 1)[1]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            def emit_task(obj):
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()

            try:
                emit_task({"stage": f"Executando MÃ³dulo de Agente: {tname}.py..."})
                res = TM.MANAGER.run_task(tname, clean_arg)
                reply = res.get("reply") or f"Tarefa `{tname}` concluÃ­da, {TITLE}."
                media_url = res.get("url")
                MEM.setdefault("history", []).append({"role": "user", "content": text})
                MEM["history"].append({"role": "assistant", "content": reply})
                save_memory()
                emit_task({
                    "action": action,
                    "token": reply,
                    "reply": reply,
                    "media_url": media_url,
                    "specialist": f"TASK:{tname}",
                    "done": True,
                })
            except Exception as e:  # noqa: BLE001
                emit_task({"error": f"Falha na tarefa {tname}: {e}", "done": True})
            return

        # Caso 1: Memorizar fato
        if action == "remember":
            MEM.setdefault("facts", []).append(clean_arg)
            save_memory()
            return self._send_sse_single("chat", f"Registrado no nÃºcleo de memÃ³ria permanente, {TITLE}: **\"{clean_arg}\"**.")

        # Caso 2: DiagnÃ³stico completo de hardware e sistemas (Ryzen 7 5700G + GTX 1660 Super)
        if action == "diagnostics":
            tel = get_telemetry()
            models = B.list_models()
            tasks = TM.MANAGER.list_tasks()
            gpu_line = (
                f"- **GPU NVIDIA:** `{tel['gpu_name']}` | Carga: `{tel['gpu_pct']}%` | Temp: `{tel['gpu_temp']} Â°C` | PotÃªncia: `{tel['gpu_power_w']} W`\n"
                f"- **VRAM Dedicada (GDDR6):** `{tel['vram_used_gb']} GB / {tel['vram_total_gb']} GB ({tel['vram_pct']}%)`\n"
                if tel.get("gpu_available")
                else "- **GPU:** `Modo CPU`\n"
            )
            rep = (
                f"Todos os sistemas do **J.A.R.V.I.S. Mark VII Pro (v{SERVER_VERSION})** estÃ£o operacionais, {TITLE}.\n\n"
                f"- **Perfil de Hardware:** `{CFG['profile'].upper()}` (`AMD Ryzen 7 5700G 8C/16T`)\n"
                f"- **Carga da CPU:** `{tel['cpu_pct']}%`\n"
                f"- **MemÃ³ria RAM:** `{tel['ram_used_gb']} GB / {tel['ram_total_gb']} GB ({tel['ram_pct']}%)`\n"
                f"{gpu_line}"
                f"- **Armazenamento Livre:** `{tel['disk_free_gb']} GB`\n"
                f"- **CÃ©rebro Neural Ativo:** `{MEM.get('active_model')}` ({len(models)} mÃ³dulos instalados)\n"
                f"- **Agentes & Tarefas DinÃ¢micas (`tasks_folder/`):** `{len(tasks)}` plugins carregados\n"
                f"- **Motor Visual & VisÃ£o HÃ­brida GPU/OCR:** `Online (Pronto)`"
            )
            return self._send_sse_single("chat", rep)

        # Caso 3: Abrir aplicativo do sistema
        if action == "open_app":
            app_map = {
                "calculadora": "calc.exe",
                "bloco de notas": "notepad.exe",
                "notepad": "notepad.exe",
                "gerenciador de tarefas": "taskmgr.exe",
                "explorador de arquivos": "explorer.exe",
                "terminal": "powershell.exe",
                "powershell": "powershell.exe",
                "cmd": "cmd.exe",
                "paint": "mspaint.exe",
            }
            exe = app_map.get(clean_arg.lower(), "explorer.exe")
            try:
                subprocess.Popen([exe], shell=True)
                return self._send_sse_single("chat", f"Imediatamente, {TITLE}. Abrindo **{clean_arg}** na sua tela.")
            except Exception as e:
                return self._send_sse_single("chat", f"NÃ£o consegui iniciar {clean_arg}, {TITLE}: {e}")

        # Caso 4: GeraÃ§Ã£o de imagem / vÃ­deo / documentÃ¡rio
        if action in ("image", "video", "documentary"):
            if action == "documentary":
                reply = f"Excelente escolha, {TITLE}. Iniciando a produÃ§Ã£o completa do documentÃ¡rio Full HD de **{minutes} minutos** sobre **{clean_arg}** com aceleraÃ§Ã£o NVENC."
                prompt = clean_arg
            else:
                reply, prompt = build_visual_prompt(clean_arg, action)
            jid = start_job(action, prompt, minutes)
            MEM.setdefault("history", []).append({"role": "user", "content": text})
            MEM["history"].append({"role": "assistant", "content": reply})
            save_memory()
            return self._send_sse_single(action, reply, job=jid, prompt=prompt, minutes=minutes)

        # Caso 5: Conversa completa em streaming (com Smart Auto-RAG e Roteamento de Especialista)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            web_ctx = ""
            if use_web or action == "web_chat":
                emit({"stage": "Consultando WikipÃ©dia PT-BR & Web em tempo real..."})
                try:
                    results = websearch.search(clean_arg, n=5)
                    web_ctx = websearch.as_context(results)
                    emit({"sources": results})
                except Exception as e:  # noqa: BLE001
                    emit({"stage": f"Modo offline: {e}"})

            chat_cfg = CFG.get("chat", {})
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            tel = get_telemetry()
            gpu_ctx = (
                f" | GPU: {tel['gpu_name']} {tel['gpu_pct']}% ({tel['gpu_temp']}Â°C, VRAM {tel['vram_used_gb']}/{tel['vram_total_gb']} GB)"
                if tel.get("gpu_available")
                else ""
            )
            sys_prompt = (
                f"{CHAT_SYS}\n"
                f"Telemetria atual: Data/Hora: {now_str} | Perfil: {CFG['profile'].upper()} (AMD Ryzen 7 5700G 8C/16T) | "
                f"CPU: {tel['cpu_pct']}% | RAM: {tel['ram_used_gb']}/{tel['ram_total_gb']} GB ({tel['ram_pct']}%)"
                f"{gpu_ctx} | Disco Livre: {tel['disk_free_gb']} GB."
            )
            if MEM.get("facts"):
                facts_txt = "\n".join(f"- {f}" for f in MEM["facts"][-30:])
                sys_prompt += f"\n\nFatos memorizados sobre o {TITLE}:\n{facts_txt}"

            msgs = [{"role": "system", "content": sys_prompt}]
            msgs += trimmed_history(chat_cfg.get("history_chars", 24000))
            msgs.append({"role": "user", "content": text + web_ctx})

            avail = B.list_models()
            model = pick_specialist_model(text, avail)
            domain_id = data.get("domain") or "polyglot"
            multi_agent = bool(data.get("multi_agent"))

            if model == "jarvis-coder:latest" or multi_agent:
                dom_name, dom_desc = DOMAINS_INFO.get(domain_id, DOMAINS_INFO["polyglot"])
                emit({"stage": f"Pipeline CodeMind 3-Agentes Ativo na GPU ({dom_name})..."})
                codemind_rules = (
                    f"\n\n[MODO CODEMIND AI STUDIO ATIVO â€” Especialidade: {dom_name} ({dom_desc})]\n"
                    "Quando o pedido envolver programaÃ§Ã£o, cÃ³digo, sistema, site ou jogo, opere nos 3 estÃ¡gios:\n"
                    "1. ESTÃGIO ARQUITETO: Antes do cÃ³digo, crie um bloco <arquitetura> ... </arquitetura> com a visÃ£o geral da arquitetura e estrutura de arquivos.\n"
                    "2. ESTÃGIO DESENVOLVEDOR SÃŠNIOR: Gere cÃ³digo 100% COMPLETO e funcional (sem placeholders). "
                    "SEMPRE nomeie cada bloco de cÃ³digo no formato exato: ```linguagem:nome_do_arquivo.ext (ex: ```html:index.html ou ```python:main.py ou ```rust:src/main.rs). "
                    "Se for Web, Dashboard, Calculadora, Interface ou Jogo 2D/3D, gere um Ãºnico arquivo ```html:index.html completo (HTML + Tailwind CDN + JS) para rodar ao vivo na aba 'Preview ao Vivo'!\n"
                    "3. ESTÃGIO AUDITOR QA & SEGURANÃ‡A: Ao final, crie um bloco <auditoria> ... </auditoria> com checklist de seguranÃ§a e comandos de terminal para rodar."
                )
                msgs[0]["content"] += codemind_rules

            full = []
            for tok in B.llm_stream(
                msgs,
                model=model,
                on_cpu=chat_cfg.get("on_cpu", CFG.get("llm_on_cpu", False)),
                num_ctx=chat_cfg.get("num_ctx", 16384),
                temperature=0.20 if model == "jarvis-coder:latest" else chat_cfg.get("temperature", 0.65),
                keep_alive=chat_cfg.get("keep_alive", "15m"),
            ):
                full.append(tok)
                emit({"token": tok})

            answer = "".join(full).strip() or f"Ã€s suas ordens, {TITLE}."
            MEM.setdefault("history", []).append({"role": "user", "content": text})
            MEM["history"].append({"role": "assistant", "content": answer})
            MEM["history"] = MEM["history"][-60:]
            save_memory()
            emit({"done": True, "reply": answer, "specialist": model})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as e:  # noqa: BLE001
            try:
                emit({"error": str(e), "done": True})
            except Exception:
                pass

    def _send_sse_single(self, action, reply, job=None, prompt="", minutes=0):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            payload = {"action": action, "token": reply, "reply": reply, "done": True}
            if job:
                payload.update(job=job, prompt=prompt, minutes=minutes)
            self.wfile.write(("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def _startup_bg():
    try:
        B.ensure_ollama()
    except Exception:
        pass
    warmup_voices()


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", CFG["port"]), Handler)
    threading.Thread(target=_startup_bg, daemon=True).start()
    print(f"J.A.R.V.I.S. Mark VII v{SERVER_VERSION} [{CFG['profile'].upper()}] online em http://127.0.0.1:{CFG['port']}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Desligando, senhor.")
