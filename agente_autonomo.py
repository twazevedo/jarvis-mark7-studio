"""Agente Engenheiro de Software Autônomo Local (CodeMind + J.A.R.V.I.S.).

Cria pastas e múltiplos arquivos de código automaticamente no seu PC usando o Ollama local
(sem precisar de chave de API paga).
"""
import os
from pathlib import Path
import re
import backends as B

WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """Você é o CodeMind Ultra integrado ao J.A.R.V.I.S., um Agente Engenheiro de Software Autônomo.
Você opera em 3 estágios:
1. <arquitetura> Planejamento da arquitetura e árvore de arquivos </arquitetura>
2. Código 100% completo (nunca omita partes). Sempre coloque o cabeçalho exato:
```linguagem:caminho/do/arquivo.ext
// código completo aqui
```
3. <auditoria> Verificação de segurança e comandos para rodar o projeto </auditoria>"""


def salvar_arquivos_gerados(resposta_texto: str, pasta_destino: str = "projeto_gerado") -> list[str]:
    padrao = r"```([a-zA-Z0-9_-]+):([^\n`]+)\n([\s\S]*?)```"
    arquivos = re.findall(padrao, resposta_texto)
    salvos = []
    base = WORKSPACE_DIR / pasta_destino
    base.mkdir(parents=True, exist_ok=True)

    for _lang, filepath, codigo in arquivos:
        rel = filepath.strip().lstrip("/\\").replace("..", "_")
        caminho_completo = (base / rel).resolve()
        if base.resolve() not in caminho_completo.parents and caminho_completo != base.resolve():
            continue
        caminho_completo.parent.mkdir(parents=True, exist_ok=True)
        caminho_completo.write_text(codigo.strip() + "\n", encoding="utf-8")
        salvos.append(str(caminho_completo))
        print(f"✅ Arquivo salvo com sucesso: {caminho_completo}")
    return salvos


def executar_agente():
    print("🚀 Agente Programador Autônomo (CodeMind + J.A.R.V.I.S.) Iniciado!")
    while True:
        pedido = input("\nDescreva o software que deseja criar (ou 'sair'): ").strip()
        if not pedido or pedido.lower() == "sair":
            break
        print("⏳ Planejando arquitetura (Arquiteto + Dev Sênior + Auditor QA)...")
        full = []
        for tok in B.llm_stream(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": pedido}],
            model="jarvis-coder:latest",
            on_cpu=True,
            num_ctx=8192,
            temperature=0.2,
        ):
            print(tok, end="", flush=True)
            full.append(tok)
        conteudo = "".join(full)
        print("\n")
        salvar_arquivos_gerados(conteudo)


if __name__ == "__main__":
    executar_agente()
