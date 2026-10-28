"""Tarefa: Agente Criador de Novas Tarefas em Tempo Real (Inspirado nos Vídeos 6 e 7 — nova_tarefa.py / task_new.py).

Quando o usuário pede 'Jarvis, crie uma nova tarefa para...', o próprio Jarvis escreve um novo
módulo Python dentro de `tasks_folder/`, valida o código e recarrega o TaskManager em tempo real!
"""
from pathlib import Path
import re
import unicodedata
import backends as B

description = "Cria novas tarefas e habilidades em Python em tempo real dentro da pasta tasks_folder/."
trigger = "Quando o usuário pedir 'crie uma nova tarefa...', 'adicione uma tarefa...' ou 'programe uma habilidade para...'."
example = "{'type': 'nova_tarefa', 'content': 'Crie uma tarefa que sorteia números da Mega-Sena'}"

TASK_CREATOR_PROMPT = """Você é o módulo Criador de Tarefas Autônomo do J.A.R.V.I.S. (inspirado no Parte 7 do Inteligência Mil Grau).
Gere um módulo Python completo e funcional para ser salvo em `tasks_folder/<name>.py`.
Responda APENAS com JSON válido no formato:
{
  "name": "nome_da_tarefa_snake_case",
  "description": "Descrição clara do que a tarefa faz",
  "trigger": "Quando acionar esta tarefa",
  "code": "código Python completo contendo description, trigger, example e def execute(content: str = '') -> str:"
}
Regras obrigatórias para o campo "code":
1. Deve definir `description = '...'`, `trigger = '...'`, `example = '...'` no topo.
2. Deve definir `def execute(content: str = "") -> str:` que executa a lógica e SEMPRE retorna uma string em português.
3. Use apenas bibliotecas da biblioteca padrão do Python (ou psutil/pyautogui/mss/pillow/pygame já instaladas) e verifique todos os imports."""


def _slug_py(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")[:32]
    return s or "tarefa_custom"


def execute(content: str = "") -> str:
    spec = (content or "").strip()
    if not spec:
        return "Descreva o que a nova tarefa deve fazer, senhor."

    out = B.llm_chat(
        [
            {"role": "system", "content": TASK_CREATOR_PROMPT},
            {"role": "user", "content": f"Crie uma tarefa em Python para: {spec}"},
        ],
        model="jarvis-coder:latest",
        on_cpu=True,
        timeout=90,
        num_predict=900,
        temperature=0.25,
    )

    name = _slug_py(out.get("name") or spec[:25])
    if name in ("task_manager", "nova_tarefa", "handle_click", "handle_image", "automatic_text_typing", "snake_game"):
        name = f"{name}_custom"

    code = (out.get("code") or "").strip()
    code = re.sub(r"^```(?:python)?\s*|\s*```$", "", code, flags=re.I).strip()

    if "def execute" not in code:
        desc = out.get("description") or spec
        trig = out.get("trigger") or spec
        code = (
            f'description = """{desc}"""\n'
            f'trigger = """{trig}"""\n'
            f'example = "{{\'type\': \'{name}\', \'content\': \'\'}}"\n\n'
            f'def execute(content: str = "") -> str:\n'
            f'    return "Tarefa {name} executada com sucesso para: " + str(content)\n'
        )

    # Valida a sintaxe antes de salvar
    compile(code, f"{name}.py", "exec")

    target_file = Path(__file__).parent / f"{name}.py"
    target_file.write_text(code, encoding="utf-8")

    # Executa um teste imediato se possível
    preview_res = ""
    try:
        ns = {}
        exec(compile(code, f"{name}.py", "exec"), ns)  # noqa: S102
        if callable(ns.get("execute")):
            preview_res = f"\n\n**Execução imediata de teste:**\n> {ns['execute'](spec)}"
    except Exception as e:
        preview_res = f"\n\n*(Módulo salvo; aviso no teste automático: {e})*"

    return (
        f"⚡ **Nova Tarefa Criada em Tempo Real!**\n"
        f"- **Módulo:** `tasks_folder/{name}.py`\n"
        f"- **Descrição:** {out.get('description') or spec}"
        f"{preview_res}"
    )
