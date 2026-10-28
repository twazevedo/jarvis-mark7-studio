"""Tarefa: Visão da Tela em Tempo Real (Inspirado nos Vídeos 1 e 4 — Jarvis Enxergando a Tela)."""
import time
import pygetwindow as gw
import backends as B
import screen_vision as SV

description = "Captura e enxerga a tela do computador em tempo real, lendo textos, janelas abertas e respondendo perguntas sobre o que está na tela."
trigger = "Quando o usuário pedir para olhar a tela, ler a tela, tirar print/captura da tela ou perguntar 'o que tem na minha tela'."
example = "{'type': 'handle_image', 'content': 'O que está aparecendo na minha tela agora?'}"


def execute(content: str = "") -> dict:
    img, mon = SV.grab_screen(1)
    fname = f"{int(time.time())}_image_screen.png"
    (SV.OUT / fname).write_bytes(b"")
    img.save(SV.OUT / fname, format="PNG")
    url = f"/outputs/{fname}"

    ocr = SV.extract_screen_elements(img)
    screen_txt = (ocr.get("full_text") or "").strip()
    try:
        wins = [w.title for w in gw.getAllWindows() if w.title and w.visible][:10]
    except Exception:
        wins = []

    question = (content or "").strip() or "Descreva o que está aparecendo na minha tela agora."
    prompt = (
        f"Você está enxergando a tela do computador do senhor ({mon['width']}x{mon['height']} px).\n"
        f"Janelas visíveis: {', '.join(wins) if wins else 'N/A'}\n"
        f"Texto lido na tela via visão computacional:\n{screen_txt[:2500] or '(nenhum texto detectado)'}\n\n"
        f"Pergunta do usuário: {question}\n"
        f"Responda em português como J.A.R.V.I.S. de forma direta, clara e útil."
    )
    try:
        tokens = list(B.llm_stream(
            [{"role": "system", "content": "Você é o módulo de Visão Computacional do J.A.R.V.I.S."},
             {"role": "user", "content": prompt}],
            model=B.CFG["llm_model"],
            on_cpu=True,
            num_ctx=4096,
            temperature=0.4,
        ))
        answer = "".join(tokens).strip()
    except Exception:
        answer = f"Capturei sua tela ({mon['width']}x{mon['height']}), senhor. Janelas ativas: {', '.join(wins[:5])}."

    return {
        "reply": f"👁️ **Visão Computacional da Tela Concluída:**\n\n{answer}",
        "url": url,
    }
