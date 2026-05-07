"""Compara screenshot atual com referencia via vision LLM."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, Any

from crewai.tools import BaseTool


def _call_vision_diff(current_path: str, reference_path: str, section: str) -> str:
    from .agents import vision_llm

    cur_b64 = base64.b64encode(Path(current_path).read_bytes()).decode("ascii")
    ref_b64 = base64.b64encode(Path(reference_path).read_bytes()).decode("ascii")

    prompt = (
        f"Compare CURRENT (site entregue) com REFERENCE (alvo). Secao: {section}.\n"
        "Liste problemas concretos: espacamento, alinhamento, tipografia, cor/contraste, "
        "hierarquia, comportamento responsivo. Seja especifico (px, hex).\n\n"
        "Devolva APENAS JSON estrito (sem markdown):\n"
        '{"section": "...", "verdict": "APROVADO"|"REPROVADO", '
        '"issues": ["..."], "reference_used": "...", "current_screenshot": "..."}\n'
        "Se diferenca for cosmetica/tolerable: APROVADO. Se afetar UX/legibilidade: REPROVADO."
    )

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{cur_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ref_b64}"}},
        ],
    }]
    return vision_llm.call(messages=messages)


class VisualDiffTool(BaseTool):
    name: str = "visual_diff"
    description: str = (
        "Compara screenshot atual com referencia. Retorna veredicto APROVADO/REPROVADO "
        "+ lista de issues. Argumentos: current_path, reference_path, section."
    )

    def _run(self, current_path: str, reference_path: str, section: str) -> Dict[str, Any]:
        raw = _call_vision_diff(current_path, reference_path, section)
        try:
            out = json.loads(raw.strip())
            out.setdefault("section", section)
            out.setdefault("verdict", "APROVADO")
            out.setdefault("issues", [])
            out.setdefault("reference_used", reference_path)
            out.setdefault("current_screenshot", current_path)
            return out
        except json.JSONDecodeError:
            return {
                "section": section, "verdict": "ERRO",
                "issues": [], "parse_error": True, "raw": raw,
                "reference_used": reference_path, "current_screenshot": current_path,
            }
