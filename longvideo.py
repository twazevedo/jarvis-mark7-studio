"""Modo documentário: tema -> roteiro (LLM) -> imagens + narração -> vídeo longo (ffmpeg).

O trabalho é retomável: tudo fica em projects/<tema>-<min>m/. Se o PC desligar ou você
cancelar, repetir o mesmo pedido continua de onde parou.
"""
import json
import math
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import wave
from pathlib import Path

import backends as B
import voice

LV = B.CFG["long_video"]
PROJECTS = B.ROOT / "projects"
OUT = B.ROOT / "outputs"


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "video"


def clean(s):
    return re.sub(r"[\*\#_`\[\]\n\r]+", " ", str(s or "")).strip()


def need_tools():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado. Rode o setup.ps1 (ou 'winget install Gyan.FFmpeg') e reabra o terminal.")
    if not (B.ROOT / LV["piper_model"]).exists():
        raise RuntimeError("Voz do narrador não encontrada. Rode o setup.ps1 novamente.")


# ------------------------------------------------------------------ roteiro
def _llm(messages, num_predict=1800):
    return B.llm_chat(messages, model=LV["script_model"], on_cpu=not LV["script_on_gpu"],
                      timeout=900, num_predict=num_predict, temperature=0.75)


def make_plan(job, topic, minutes, pdir):
    plan_file = pdir / "plan.json"
    if plan_file.exists():
        plan = json.loads(plan_file.read_text(encoding="utf-8-sig"))
    else:
        job.update(stage="Estruturando o roteiro", done=0, total=1)
        n_chap = max(2, min(minutes, 20))
        total = max(3, round(minutes * LV["scenes_per_minute"]))
        sys_msg = {"role": "system", "content": "Você é um roteirista de documentários em português do Brasil."}
        chapters, title = [], topic
        for _ in range(3):
            out = _llm([sys_msg, {"role": "user", "content":
                f"Tema do documentário: {topic}\nCrie a estrutura com exatamente {n_chap} capítulos em ordem lógica "
                f"(introdução, desenvolvimento, conclusão). Responda só JSON: "
                f'{{"titulo": "título curto", "capitulos": ["título do capítulo", ...]}}'}], 600)
            title = clean(out.get("titulo")) or topic
            chapters = []
            for c in out.get("capitulos", []):
                chapters.append(clean(" ".join(map(str, c.values())) if isinstance(c, dict) else c))
            chapters = [c for c in chapters if c][:n_chap]
            if len(chapters) >= max(2, n_chap // 2):
                break
        if not chapters:
            chapters = [f"{topic} — parte {i + 1}" for i in range(n_chap)]
        plan = {"title": title, "topic": topic, "minutes": minutes, "chapter_titles": chapters,
                "per": math.ceil(total / len(chapters)), "chapters": []}
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    titles = plan["chapter_titles"]
    outline = "; ".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    words = LV["words_per_scene"]
    while len(plan["chapters"]) < len(titles):
        ci = len(plan["chapters"])
        job.update(stage=f"Escrevendo roteiro — capítulo {ci + 1}/{len(titles)}", done=ci, total=len(titles))
        prev = plan["chapters"][-1][-1]["narration"] if ci and plan["chapters"][-1] else ""
        scenes = []
        for _ in range(5):
            need = plan["per"] - len(scenes)
            if need <= 0:
                break
            ask = (f"Documentário: \"{plan['title']}\" (tema: {topic}).\nEstrutura: {outline}\n"
                   f"Agora escreva o capítulo {ci + 1}: \"{titles[ci]}\".\n"
                   + (f"Narração da cena anterior (continue a partir dela, sem repetir): \"{prev}\"\n" if prev else "")
                   + f"Escreva {need} cenas consecutivas. Cada cena tem: "
                   f"\"narracao\" — texto falado em português do Brasil, fluido e informativo, com cerca de {words} palavras, "
                   f"sem listas, sem marcações e sem citar 'cena' ou 'capítulo'; "
                   f"\"visual\" — descrição da imagem em INGLÊS (sujeito, ambiente, luz, ângulo de câmera), "
                   f"sem texto escrito e sem pessoas famosas reais.\n"
                   f'Responda só JSON: {{"cenas": [{{"narracao": "...", "visual": "..."}}]}}')
            try:
                data = _llm([sys_msg_scene(), {"role": "user", "content": ask}])
            except Exception as e:  # noqa: BLE001
                if "connect" in str(e).lower() or "refused" in str(e).lower():
                    raise RuntimeError("Não consegui falar com o Ollama. Ele está rodando?")
                continue
            for s in data.get("cenas", []):
                if not isinstance(s, dict):
                    continue
                n, v = clean(s.get("narracao")), clean(s.get("visual"))
                if len(n.split()) >= 8 and len(v) >= 10:
                    scenes.append({"narration": n, "visual": v})
                    prev = n
        scenes = scenes[:plan["per"]]
        if not scenes:
            raise RuntimeError(f"O modelo '{LV['script_model']}' não conseguiu escrever o capítulo {ci + 1}. "
                               f"Ele está instalado? (ollama pull {LV['script_model']})")
        plan["chapters"].append(scenes)
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return plan


def sys_msg_scene():
    return {"role": "system", "content": "Você é um roteirista de documentários em português do Brasil. "
            "Escreve narração envolvente, correta e clara. Responde sempre em JSON válido."}


# ------------------------------------------------------------------ mídia
def tts(text, wav: Path, voice_mode: str = "jarvis_br"):
    voice.synthesize_to_wav(text, wav, voice_mode=voice_mode)


def wav_len(wav: Path):
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def _motion_vf(idx, n, dur, W, H, fps):
    """Filtro de vídeo: recorte 16:9, zoom/pan suave (4 variações) e fade in/out."""
    c = "x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
    zoompan = [
        f"z='1+0.18*on/{n}':{c}",
        f"z='1.18-0.18*on/{n}':{c}",
        f"z='1.15':x='(iw-iw/zoom)*(1-on/{n})':y='(ih-ih/zoom)/2'",
        f"z='1.15':x='(iw-iw/zoom)*on/{n}':y='(ih-ih/zoom)/2'",
    ][idx % 4]
    return (f"scale={W * 2}:{H * 2}:flags=lanczos:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
            f"zoompan={zoompan}:d={n}:s={W}x{H}:fps={fps},"
            f"fade=t=in:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4,format=yuv420p")


def render_clip(png: Path, wav: Path, out: Path, idx: int):
    W, H, fps = LV["video_width"], LV["video_height"], LV["fps"]
    dur = wav_len(wav) + 0.7
    n = max(1, round(dur * fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-i", str(wav),
           "-vf", _motion_vf(idx, n, dur, W, H, fps),
           "-af", "apad=pad_dur=0.7,aresample=44100", "-t", f"{dur:.2f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", str(fps),
           "-c:a", "aac", "-b:a", "160k", "-ac", "2", str(out)]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + p.stderr.decode(errors="replace")[-400:])
    return dur


def animate_still(png: Path, out: Path, seconds=6, idx=0):
    """Vídeo curto sem áudio a partir de uma imagem (movimento de câmera). Usado no perfil lite."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado. Rode o setup.ps1 (ou 'winget install Gyan.FFmpeg') e reabra o terminal.")
    W, H, fps = LV["video_width"], LV["video_height"], LV["fps"]
    n = max(1, round(seconds * fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-vf", _motion_vf(idx, n, seconds, W, H, fps),
           "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", str(fps),
           "-an", "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + p.stderr.decode(errors="replace")[-400:])


def fmt_srt(t):
    h, r = divmod(int(t * 1000), 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ------------------------------------------------------------------ principal
def build(job, topic, minutes):
    """Executa todo o pipeline. Retorna a URL relativa (/outputs/...) do vídeo final."""
    need_tools()
    OUT.mkdir(exist_ok=True)
    pdir = PROJECTS / f"{slug(topic)}-{minutes}m"
    (pdir / "scenes").mkdir(parents=True, exist_ok=True)

    plan = make_plan(job, topic, minutes, pdir)
    scenes = [s for ch in plan["chapters"] for s in ch]
    n = len(scenes)
    img_cfg = {**B.CFG["image"], **LV["image"]}
    style = LV["style"]

    durations = []
    for i, sc in enumerate(scenes):
        job.update(stage=f"Narrando e ilustrando — cena {i + 1}/{n}", done=i, total=n)
        wav, png, clip = (pdir / "scenes" / f"{i:03d}.{e}" for e in ("wav", "png", "mp4"))
        if not wav.exists():
            tts(sc["narration"], wav, voice_mode=job.get("voice_mode", "jarvis_br"))
        if not png.exists():
            data, _ = B.generate_image(f"{sc['visual']}, {style}", cfg=img_cfg)
            png.write_bytes(data)
    for i, sc in enumerate(scenes):
        job.update(stage=f"Montando cenas — {i + 1}/{n}", done=i, total=n)
        wav, png, clip = (pdir / "scenes" / f"{i:03d}.{e}" for e in ("wav", "png", "mp4"))
        if not clip.exists():
            render_clip(png, wav, clip, i)
        durations.append(wav_len(wav) + 0.7)

    job.update(stage="Unindo o vídeo final", done=n, total=n)
    lst = pdir / "list.txt"
    lst.write_text("".join(f"file '{(pdir / 'scenes' / f'{i:03d}.mp4').as_posix()}'\n" for i in range(n)), encoding="utf-8")
    joined = pdir / "joined.mp4"
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(joined)], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (união) falhou: " + p.stderr.decode(errors="replace")[-400:])

    final = joined
    music = B.ROOT / LV.get("music", "")
    if LV.get("music") and music.is_file():
        job.update(stage="Mixando a trilha sonora")
        mixed = pdir / "mixed.mp4"
        p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
                            "-filter_complex", "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(mixed)],
                           capture_output=True)
        if p.returncode == 0:
            final = mixed

    name = f"{int(time.time())}_movie_{slug(plan['title'])}"
    shutil.copy(final, OUT / f"{name}.mp4")
    t, cues = 0.0, []
    for i, (sc, d) in enumerate(zip(scenes, durations), 1):
        cues.append(f"{i}\n{fmt_srt(t)} --> {fmt_srt(t + d - 0.7)}\n{sc['narration']}\n")
        t += d
    (OUT / f"{name}.srt").write_text("\n".join(cues), encoding="utf-8")
    job["duration"] = int(t)
    return f"/outputs/{name}.mp4"
