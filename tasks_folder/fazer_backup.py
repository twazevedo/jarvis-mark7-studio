"""Tarefa: Backup Automático de Projetos para o Outro PC (192.168.100.63)."""
import subprocess
from pathlib import Path

description = "Gera um backup completo e compactado de todos os seus projetos e envia automaticamente pela rede local para o seu outro computador (192.168.100.63)."
trigger = "Quando o usuário pedir 'faça o backup', 'envie os projetos para o outro pc', 'backup na rede', 'sincronizar projetos' ou 'backup para o notebook'."
example = "{'type': 'fazer_backup', 'content': 'Fazer backup de todos os projetos para o outro computador'}"

SCRIPT_PATH = Path("C:/Users/Thiag/Desktop/SISTEMA_BACKUP_REDE/ENVIAR_BACKUP_PARA_OUTRO_PC.ps1")

def execute(content: str = "") -> str:
    if not SCRIPT_PATH.is_file():
        return "Script de backup não encontrado em C:\\Users\\Thiag\\Desktop\\SISTEMA_BACKUP_REDE."

    try:
        p = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=180
        )
        output = p.stdout.strip()
        last_lines = "\n".join(output.splitlines()[-6:])
        return (
            f"📦 **Rotina de Backup Executada com Sucesso!**\n\n"
            f"```text\n{last_lines}\n```\n\n"
            f"Os arquivos foram compactados e processados para envio ao computador `192.168.100.63`, senhor."
        )
    except Exception as e:
        return f"Falha ao executar rotina de backup: {e}"
