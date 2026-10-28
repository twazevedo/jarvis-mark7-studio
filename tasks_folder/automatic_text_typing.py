"""Tarefa: Digitação Automática e Controle de Teclado (Inspirado nos Vídeos 4 e 6 — automatic_text_typing.py)."""
import re
import time
import pyautogui
import pyperclip

pyautogui.FAILSAFE = False

description = "Recebe um texto e utiliza automação em Python para digitar esse texto automaticamente onde o cursor estiver."
trigger = "Quando o usuário pedir 'digite automaticamente...', 'escreva na tela...' ou 'digite o texto...'."
example = "{'type': 'automatic_text_typing', 'content': 'Texto que você deseja digitar.'}"


def funcao_digitacao(texto: str) -> str:
    clean = re.sub(
        r"^(?:jarvis[, ]*)?(?:por favor[, ]*)?(?:digite automaticamente|digite na tela|digite o texto|digite|escreva na tela)[: ]*",
        "", (texto or "").strip(), flags=re.I
    ).strip() or texto
    if not clean:
        return "Nenhum texto informado para digitação, senhor."
    time.sleep(0.35)
    try:
        pyperclip.copy(clean)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
    except Exception:
        pyautogui.write(clean, interval=0.02)
        pyautogui.press("enter")
    return f"⌨️ Texto digitado automaticamente com sucesso, senhor: **\"{clean}\"**."


def execute(content: str = "") -> str:
    return str(funcao_digitacao(content))
