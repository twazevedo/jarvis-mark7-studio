"""Gerenciador Dinâmico de Tarefas e Agentes (Inspirado na série Jarvis / Junin v8 — Inteligência Mil Grau).

Carrega dinamicamente todos os módulos Python de `tasks_folder/*.py` que possuem:
- description: descrição da tarefa
- trigger: quando acionar a tarefa
- example: exemplo de chamada
- execute(content): função principal que executa a ação e retorna dict ou str
"""
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("JarvisTaskManager")

ROOT = Path(__file__).parent
TASKS_DIR = ROOT / "tasks_folder"
TASKS_DIR.mkdir(exist_ok=True)


class TaskManager:
    def __init__(self, tasks_path: Path = TASKS_DIR):
        self.tasks_path = Path(tasks_path)
        self.tasks_path.mkdir(exist_ok=True)
        self.task_handlers: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> Dict[str, Dict[str, Any]]:
        """Recarrega dinamicamente todos os plugins de tarefas em tasks_folder/ sem reiniciar o Jarvis."""
        handlers: Dict[str, Dict[str, Any]] = {}
        for filepath in sorted(self.tasks_path.glob("*.py")):
            if filepath.name in ("__init__.py", "task_manager.py"):
                continue
            task_name = filepath.stem
            try:
                spec = importlib.util.spec_from_file_location(f"tasks_folder.{task_name}", str(filepath))
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                execute_func = getattr(module, "execute", None)
                if not callable(execute_func):
                    continue
                handlers[task_name] = {
                    "name": task_name,
                    "file": filepath.name,
                    "description": str(getattr(module, "description", "Sem descrição.")).strip(),
                    "trigger": str(getattr(module, "trigger", "Sem gatilho.")).strip(),
                    "example": str(getattr(module, "example", "")).strip(),
                    "execute": execute_func,
                }
            except Exception as e:  # noqa: BLE001
                log.warning("Erro ao carregar tarefa %s: %s", task_name, e)
        self.task_handlers = handlers
        return handlers

    def list_tasks(self) -> list[dict]:
        """Retorna os metadados de todas as tarefas instaladas para exibição no HUD."""
        self.reload()
        return [
            {
                "name": k,
                "file": v["file"],
                "description": v["description"],
                "trigger": v["trigger"],
                "example": v["example"],
            }
            for k, v in self.task_handlers.items()
        ]

    def run_task(self, task_name: str, content: str = "") -> dict:
        """Executa uma tarefa específica pelo nome e retorna {'reply': str, 'url': optional_media_url}."""
        self.reload()
        handler = self.task_handlers.get(task_name)
        if not handler:
            return {"reply": f"A tarefa `{task_name}` não foi encontrada em `tasks_folder/`."}
        res = handler["execute"](content)
        if isinstance(res, dict):
            return res
        return {"reply": str(res)}


MANAGER = TaskManager()
