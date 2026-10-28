"""Tarefa: Enxergar Objeto/Texto na Tela e Clicar Automaticamente (Inspirado nos Vídeos 1, 2 e 4 — Molmo & Junin Click)."""
import re
import pyautogui
import backends as B
import screen_vision as SV

pyautogui.FAILSAFE = False

description = "Localiza qualquer botão, texto, ícone ou coordenada na tela e clica automaticamente com o mouse."
trigger = "Quando o usuário pedir 'clique em...', 'clica no...', 'aponte para...' ou informar coordenadas na tela."
example = "{'type': 'handle_click', 'content': 'Clique em Enviar'}"


def _find_target_coords(target: str, items: list[dict], width: int, height: int) -> tuple[int, int, str]:
    tl = target.lower().strip()

    # 1) Coordenadas explícitas (ex: "500, 300" ou "500x300")
    m_xy = re.search(r"(\d{2,4})\s*[,xX ]\s*(\d{2,4})", tl)
    if m_xy:
        x = min(max(5, int(m_xy.group(1))), width - 5)
        y = min(max(5, int(m_xy.group(2))), height - 5)
        return x, y, f"coordenada ({x}, {y})"

    # 2) Posições geométricas da tela
    if "centro" in tl or "meio da tela" in tl:
        return width // 2, height // 2, "centro da tela"
    if "canto superior direito" in tl:
        return width - 60, 40, "canto superior direito"
    if "canto superior esquerdo" in tl:
        return 60, 40, "canto superior esquerdo"
    if "canto inferior direito" in tl:
        return width - 60, height - 40, "canto inferior direito"
    if "canto inferior esquerdo" in tl or "iniciar" in tl:
        return 40, height - 25, "canto inferior esquerdo"

    # 3) Busca direta nos elementos detectados na tela pelo OCR com coordenadas
    clean_target = re.sub(
        r"^(?:jarvis[, ]*)?(?:por favor[, ]*)?(?:clique|clica|clicar|aponte|aperte)\s+(?:em|no|na|nos|nas|sobre|o|a)?\s*",
        "", tl, flags=re.I
    ).strip(" \"'.,!?") or tl

    for it in items:
        txt = (it.get("text") or "").lower().strip()
        if clean_target and (clean_target == txt or clean_target in txt):
            return int(it["x"]), int(it["y"]), f"'{it.get('text')}'"

    # 4) Se não achou por substring exata, usa o LLM para escolher o elemento mais próximo da lista de coordenadas da tela
    if items:
        candidates = [f"[{i}] '{it['text']}' em ({it['x']},{it['y']})" for i, it in enumerate(items[:80]) if not it.get("word")]
        if candidates:
            try:
                ans = B.llm_chat(
                    [
                        {"role": "system", "content": "Escolha o elemento da tela que corresponde ao pedido de clique do usuário. Responda SÓ JSON: {\"x\": int, \"y\": int, \"label\": \"texto\"}"},
                        {"role": "user", "content": f"Alvo pedido: {clean_target}\nElementos visíveis na tela:\n" + "\n".join(candidates)},
                    ],
                    timeout=15,
                    num_predict=80,
                    temperature=0.1,
                )
                if ans.get("x") and ans.get("y"):
                    return int(ans["x"]), int(ans["y"]), str(ans.get("label") or clean_target)
            except Exception:
                pass

    return -1, -1, clean_target


def execute(content: str = "") -> dict:
    img, mon = SV.grab_screen(1)
    W, H = mon["width"], mon["height"]
    ocr = SV.extract_screen_elements(img)
    items = ocr.get("items", [])

    x, y, matched = _find_target_coords(content, items, W, H)
    if x < 0 or y < 0:
        url = SV.save_annotated_click(img, W // 2, H // 2, "não localizado")
        return {
            "reply": f"Examinei sua tela ({W}x{H}), senhor, mas não encontrei um elemento visível com o texto **\"{matched}\"**. Verifique se a janela desejada está visível.",
            "url": url,
        }

    abs_x = mon["left"] + x
    abs_y = mon["top"] + y
    url = SV.save_annotated_click(img, x, y, matched)
    try:
        pyautogui.moveTo(abs_x, abs_y, duration=0.35)
        pyautogui.click(abs_x, abs_y)
    except Exception as e:
        return {"reply": f"Localizei **{matched}** em `({x}, {y})`, mas o clique falhou: {e}", "url": url}

    return {
        "reply": f"🎯 **Alvo Localizado e Clicado!**\nMirei em **{matched}** nas coordenadas `X={x}, Y={y}` e executei o clique, senhor. Veja a marcação da mira na captura gerada.",
        "url": url,
    }
