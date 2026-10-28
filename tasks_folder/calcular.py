"""Tarefa: Calculadora Científica & Geometria (Inspirado nos Vídeos 6 e 7 — calcular.py / calcular_area_circulo.py)."""
import math
import re

description = "Executa cálculos matemáticos exatos, porcentagens, potências, raízes, trigonometria e área de figuras."
trigger = "Quando o usuário pedir para calcular uma expressão matemática, área de círculo ou fórmula exata."
example = "{'type': 'calcular', 'content': 'area circulo raio 12'}"


def execute(content: str = "") -> str:
    tl = (content or "").lower().strip()
    m_circ = re.search(r"(?:[aá]rea\s+(?:do\s+)?c[ií]rculo).*?(\d+(?:[.,]\d+)?)", tl)
    if m_circ:
        r = float(m_circ.group(1).replace(",", "."))
        area = math.pi * (r ** 2)
        return f"📐 A área do círculo de raio `{r}` é **`{area:.4f}`** ($\\pi \\times {r}^2$)."

    expr = re.sub(r"[^0-9+\-*/().,%^ ]", "", tl.replace(",", ".").replace("^", "**")).strip()
    if expr and any(c.isdigit() for c in expr):
        try:
            res = eval(expr, {"__builtins__": None}, {"math": math, "pi": math.pi, "sqrt": math.sqrt})  # noqa: S307
            return f"🧮 Resultado exato de `{expr}` = **`{res}`**, senhor."
        except Exception as e:
            return f"Não foi possível avaliar a expressão `{expr}`: {e}"
    return "Informe os números ou a expressão que deseja calcular, senhor."
