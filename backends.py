"""Acesso aos backends locais: Ollama (LLM + Visão GPU), ComfyUI (GPU NVIDIA GTX 1660 Super) e stable-diffusion.cpp (CPU).

Perfis (profiles/*.json são mesclados sobre config.json):
  pro  -> PC Ryzen 7 5700G (8C/16T) + GTX 1660 Super (6 GB VRAM): ComfyUI (--lowvram --fp32-vae), LLM 7B/8B na GPU e NVENC Full HD
  lite -> PC só com CPU: stable-diffusion.cpp (SD 1.5 + LCM, 4 passos) e LLM 3B na CPU
Escolha com a variável JARVIS_PROFILE (pro|lite). Sem ela: 'pro' se houver nvidia-smi, senão 'lite'.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import workflows

ROOT = Path(__file__).parent


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _load():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    name = os.environ.get("JARVIS_PROFILE") or ("pro" if shutil.which("nvidia-smi") else "lite")
    prof = ROOT / "profiles" / f"{name}.json"
    if not prof.exists():
        raise SystemExit(f"Perfil '{name}' não existe (use pro ou lite).")
    cfg = _merge(cfg, json.loads(prof.read_text(encoding="utf-8-sig")))
    cfg["profile"] = name
    return cfg


CFG = _load()

# Ferramentas portáteis (instaladas pelo Jarvis.exe / setup.ps1) entram no PATH deste processo e dos filhos.
for _d in (ROOT / "tools" / "ffmpeg" / "bin", ROOT / "tools" / "ffmpeg"):
    if (_d / "ffmpeg.exe").is_file():
        os.environ["PATH"] = str(_d) + os.pathsep + os.environ.get("PATH", "")
        break

# Uma geração por vez (GPU de 6 GB / CPU). O lock é por imagem/clipe, então pedidos
# rápidos conseguem "furar a fila" entre as cenas de um documentário longo.
GEN_LOCK = threading.Lock()


# ------------------------------------------------------------------ HTTP
def http_json(url, data=None, timeout=30):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw.strip() else {}


def http_bytes(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def reachable(url, timeout=4.0):
    try:
        urllib.request.urlopen(url, timeout=timeout).read()
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ LLM & Visão
def ensure_ollama():
    """Garante que o servidor do Ollama esteja rodando em segundo plano com otimização para 6 GB VRAM."""
    if reachable(CFG["ollama_url"] + "/api/tags", timeout=1.5):
        return True
    candidates = [
        shutil.which("ollama"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
    ]
    exe = next((c for c in candidates if c and Path(c).is_file()), None)
    if not exe:
        return False
    try:
        env = os.environ.copy()
        env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
        env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.Popen([exe, "serve"], env=env, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(25):
            time.sleep(0.4)
            if reachable(CFG["ollama_url"] + "/api/tags", timeout=1.5):
                return True
    except Exception:
        pass
    return False


def _default_opts(on_cpu=None, temperature=0.6, num_ctx=None, num_predict=None) -> dict:
    use_cpu = CFG.get("llm_on_cpu", False) if on_cpu is None else bool(on_cpu)
    opts = {
        "temperature": temperature,
        "num_thread": CFG.get("cpu_threads", max(4, min(12, (os.cpu_count() or 8) - 2))),
    }
    if use_cpu:
        opts["num_gpu"] = 0
    if num_ctx:
        opts["num_ctx"] = num_ctx
    if num_predict:
        opts["num_predict"] = num_predict
    return opts


def llm_chat(messages, model=None, on_cpu=None, timeout=180, num_predict=None, temperature=0.6):
    """Chama o Ollama pedindo JSON e devolve o objeto já decodificado."""
    ensure_ollama()
    opts = _default_opts(on_cpu=on_cpu, temperature=temperature, num_predict=num_predict)
    body = {
        "model": model or CFG["llm_model"],
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": opts,
    }
    if CFG.get("low_memory"):
        body["keep_alive"] = 0
    r = http_json(f"{CFG['ollama_url']}/api/chat", body, timeout=timeout)
    content = r.get("message", {}).get("content", "{}")
    return json.loads(content)


def llm_vision(image_b64: str, prompt: str, timeout: int = 60) -> str:
    """Analisa uma imagem em Base64 usando um modelo multimodal (ex: moondream) na GPU se instalado."""
    ensure_ollama()
    models = list_models()
    vision_candidates = [
        CFG.get("vision_model", "moondream:latest"),
        "moondream:latest",
        "moondream",
        "llava-phi3:latest",
        "llava:latest",
        "minicpm-v:latest",
    ]
    vmodel = next((m for m in vision_candidates if m in models), None)
    if not vmodel:
        return ""
    body = {
        "model": vmodel,
        "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
        "stream": False,
        "keep_alive": "2m",
        "options": _default_opts(on_cpu=False, temperature=0.2, num_predict=300),
    }
    try:
        r = http_json(f"{CFG['ollama_url']}/api/chat", body, timeout=timeout)
        return (r.get("message", {}).get("content") or "").strip()
    except Exception:
        return ""


def llm_stream(messages, model, on_cpu=None, num_ctx=None, temperature=0.65, keep_alive="15m"):
    """Conversa livre em streaming: gera pedaços de texto (tokens) à medida que o Ollama produz."""
    ensure_ollama()
    ctx = num_ctx or CFG.get("chat", {}).get("num_ctx", 16384)
    opts = _default_opts(on_cpu=on_cpu, temperature=temperature, num_ctx=ctx)
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": keep_alive,
        "options": opts,
    }).encode()
    req = urllib.request.Request(
        f"{CFG['ollama_url']}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            for line in r:
                if not line.strip():
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise RuntimeError(d["error"])
                t = d.get("message", {}).get("content", "")
                if t:
                    yield t
                if d.get("done"):
                    return
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code == 404:
            raise RuntimeError(f"O modelo '{model}' não está instalado. Instale com: ollama pull {model}")
        raise RuntimeError(f"Ollama respondeu {e.code}: {detail[:200]}")
    except urllib.error.URLError:
        raise RuntimeError("Não consegui falar com o Ollama. Ele está rodando?")


def list_models():
    try:
        return [m["name"] for m in http_json(f"{CFG['ollama_url']}/api/tags", timeout=3).get("models", [])]
    except Exception:
        return []


def free_llm():
    """Descarrega os modelos do Ollama da VRAM (6 GB GTX 1660 Super) antes de gerar imagens/vídeos."""
    if not CFG.get("unload_before_generate", True):
        return
    try:
        for m in http_json(f"{CFG['ollama_url']}/api/ps", timeout=2).get("models", []):
            http_json(f"{CFG['ollama_url']}/api/generate", {"model": m["name"], "keep_alive": 0}, timeout=10)
    except Exception:
        pass


def free_comfy_vram():
    """Libera os modelos do ComfyUI da VRAM após concluir a geração, devolvendo os 6 GB para o LLM."""
    if CFG["backend"] != "comfy":
        return
    try:
        http_json(f"{CFG['comfy_url']}/free", {"unload_models": True, "free_memory": True}, timeout=5)
    except Exception:
        pass


def ensure_comfyui():
    """Inicia automaticamente o ComfyUI com --lowvram --fp32-vae (ideal para GTX 1660 Super 6 GB) se não estiver ativo."""
    if CFG["backend"] != "comfy":
        return False
    if reachable(CFG["comfy_url"] + "/system_stats", timeout=2.0):
        return True
    comfy_dir = ROOT / "ComfyUI"
    comfy_py = comfy_dir / "venv" / "Scripts" / "python.exe"
    if not comfy_py.is_file() or not (comfy_dir / "main.py").is_file():
        return False
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        args = [str(comfy_py), "main.py", "--lowvram", "--fp32-vae", "--listen", "127.0.0.1", "--port", "8188"]
        subprocess.Popen(args, cwd=str(comfy_dir), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(45):
            time.sleep(1.0)
            if reachable(CFG["comfy_url"] + "/system_stats", timeout=2.0):
                return True
    except Exception:
        pass
    return False


# ------------------------------------------------------------------ Imagens & Vídeos
def generator_ready():
    """True se o gerador de imagens do perfil está pronto para uso."""
    if CFG["backend"] == "comfy":
        return reachable(CFG["comfy_url"] + "/system_stats") or (ROOT / "ComfyUI" / "main.py").is_file()
    c = CFG["image"]
    return (ROOT / c["binary"]).is_file() and (ROOT / c["checkpoint"]).is_file()


def generate_image(prompt, cfg=None, keep_vram=False):
    """Gera uma imagem e devolve (bytes, nome_do_arquivo). Levanta RuntimeError."""
    cfg = cfg or CFG["image"]
    if CFG["backend"] == "comfy":
        return comfy_generate("image", prompt, cfg, keep_vram=keep_vram)
    return sdcpp_generate(prompt, cfg)


def sdcpp_generate(prompt, cfg):
    exe, model = ROOT / cfg["binary"], ROOT / cfg["checkpoint"]
    if not exe.is_file() or not model.is_file():
        raise RuntimeError("stable-diffusion.cpp ou o modelo não foram encontrados. Rode o setup.ps1 -Profile lite.")
    lora = cfg.get("lora")
    text = f"{prompt} <lora:{lora}:1>" if lora else prompt
    threads = cfg.get("threads") or max(1, (os.cpu_count() or 4) - 2)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.png"
        cmd = [
            str(exe), "-m", str(model), "-p", text, "--steps", str(cfg["steps"]),
            "--cfg-scale", str(cfg["cfg"]), "--sampling-method", cfg["sampler"],
            "-W", str(cfg["width"]), "-H", str(cfg["height"]), "-t", str(threads),
            "-s", "-1", "-o", str(out),
        ]
        if cfg.get("vae_tiling"):
            cmd.append("--vae-tiling")
        if lora:
            cmd += ["--lora-model-dir", str(ROOT / cfg["lora_dir"])]
        free_llm()
        with GEN_LOCK:
            p = subprocess.run(cmd, capture_output=True, cwd=str(exe.parent))
        if p.returncode != 0 or not out.exists():
            tail = (p.stderr or p.stdout).decode(errors="replace")[-400:]
            raise RuntimeError(f"stable-diffusion.cpp falhou: {tail}")
        return out.read_bytes(), "sd.png"


def comfy_generate(kind, prompt, cfg=None, timeout_s=3 * 3600, keep_vram=False):
    """Gera uma imagem/vídeo no ComfyUI (GTX 1660 Super) e devolve (bytes, nome_do_arquivo)."""
    cfg = cfg or CFG[kind]
    ensure_comfyui()
    wf = (workflows.image_workflow if kind == "image" else workflows.video_workflow)(prompt, cfg)
    free_llm()
    with GEN_LOCK:
        try:
            try:
                res = http_json(f"{CFG['comfy_url']}/prompt", {"prompt": wf, "client_id": "jarvis"})
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")
                try:
                    j = json.loads(detail)
                    detail = j.get("error", {}).get("message", "") or detail
                    for n in j.get("node_errors", {}).values():
                        for er in n.get("errors", []):
                            detail += f" | {er.get('message')}: {er.get('details')}"
                except Exception:
                    pass
                raise RuntimeError(f"ComfyUI recusou o workflow: {detail[:400]}")
            pid = res["prompt_id"]
            t0 = time.time()
            while time.time() - t0 < timeout_s:
                time.sleep(1.5)
                hist = http_json(f"{CFG['comfy_url']}/history/{pid}").get(pid)
                if not hist:
                    continue
                st = hist.get("status", {})
                if st.get("status_str") == "error":
                    msg = "erro durante a geração (veja o console do ComfyUI)"
                    for ev in st.get("messages", []):
                        if ev[0] == "execution_error":
                            msg = ev[1].get("exception_message", msg)
                    raise RuntimeError(msg.strip())
                files = [im for o in hist.get("outputs", {}).values() for im in o.get("images", [])]
                if files:
                    im = files[0]
                    q = urllib.parse.urlencode({
                        "filename": im["filename"],
                        "subfolder": im.get("subfolder", ""),
                        "type": im.get("type", "output"),
                    })
                    data = http_bytes(f"{CFG['comfy_url']}/view?{q}", timeout=120)
                    if not keep_vram:
                        free_comfy_vram()
                    return data, im["filename"]
            raise RuntimeError("tempo esgotado esperando o ComfyUI")
        except urllib.error.URLError:
            raise RuntimeError("Não consegui falar com o ComfyUI. Rode o setup.ps1 -Profile pro ou inicie o ComfyUI.")
