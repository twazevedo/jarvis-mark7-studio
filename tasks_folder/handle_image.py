"""Tarefa: Visão Computacional Híbrida da Tela em Tempo Real (Visão Multimodal GPU + OCR Windows)."""
import base64
import io
import time
import pygetwindow as gw
import backends as B
import screen_vision as SV

description = "Captura e enxerga a tela do computador em tempo real usando Visão Multimodal na GPU + OCR nativo, lendo imagens, ícones, textos e janelas abertas."
trigger = "Quando o usuário pedir para olhar a tela, ler a tela, tirar print/captura da tela ou perguntar 'o que tem na minha tela'."
example = "{'type': 'handle_image', 'content': 'O que está aparecendo na minha tela agora?'}"


def execute(content: str = "") -> dict:
    img, mon = SV.grab_screen(1)
    fname = f"{int(time.time())}_image_screen.png"
    out_path = SV.OUT / fname
    img.save(out_path, format="PNG")
    url = f"/outputs/{fname}"

    # 1) OCR Nativo do Windows 10/11 (textos exatos e coordenadas)
    ocr = SV.extract_screen_elements(img)
    screen_txt = (ocr.get("full_text") or "").strip()
    try:
        wins = [w.title for w in gw.getAllWindows() if w.title and w.visible][:12]
    except Exception:
        wins = []

    # 2) Visão Multimodal na GPU (moondream / llava) se instalado no Ollama
    vision_desc = ""
    try:
        thumb = img.copy()
        thumb.thumbnail((1280, 720))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        vision_desc = B.llm_vision(
            b64,
            "Describe the visual layout, applications, images, colors, and main elements visible on this computer screen concisely.",
            timeout=35,
        )
    except Exception:
        vision_desc = ""

    question = (content or "").strip() or "Descreva detalhadamente o que está aparecendo na minha tela agora."
    prompt = (
        f"Você está enxergando a tela do computador do senhor ({mon['width']}x{mon['height']} px).\n"
        f"Janelas ativas no Windows: {', '.join(wins) if wins else 'N/A'}\n"
        + (f"Percepção Visual Multimodal (GPU Vision): {vision_desc}\n" if vision_desc else "")
        + f"Texto lido na tela via OCR nativo:\n{screen_txt[:3200] or '(nenhum texto detectado)'}\n\n"
        f"Pergunta/Comando do usuário: {question}\n"
        f"Responda em português do Brasil como J.A.R.V.I.S. de forma direta, elegante e precisa."
    )
    try:
        tokens = list(B.llm_stream(
            [{"role": "system", "content": "Você é o módulo de Visão Computacional Híbrida (GPU + OCR) do J.A.R.V.I.S."},
             {"role": "user", "content": prompt}],
            model=B.CFG["llm_model"],
            on_cpu=B.CFG.get("llm_on_cpu", False),
            num_ctx=8192,
            temperature=0.35,
        ))
        answer = "".join(tokens).strip()
    except Exception:
        answer = f"Capturei sua tela ({mon['width']}x{mon['height']}), senhor. Janelas ativas: {', '.join(wins[:5])}."

    return {
        "reply": f"👁️ **Visão Computacional da Tela Concluída ({mon['width']}x{mon['height']}):**\n\n{answer}",
        "url": url,
    }
