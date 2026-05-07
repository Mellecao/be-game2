"""Analisa imagem via vision LLM, retorna JSON estruturado."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, Any

from crewai.tools import BaseTool
from pydantic import Field


def _call_vision(image_path: str, context: str) -> str:
    """Chama vision_llm com a imagem encoded em base64."""
    from .agents import vision_llm

    img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    prompt = (
        f"Analise esta imagem ({context}). Devolva APENAS JSON estrito:\n"
        '{"tipografia": "...", "cores": ["#hex", ...], '
        '"layout": "...", "cta": "...", "padroes": ["..."]}\n'
        "Sem hedge, sem markdown, sem explicacao."
    )
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ],
    }]
    return vision_llm.call(messages=messages)


class VisionAnalysisTool(BaseTool):
    name: str = "vision_analyze"
    description: str = (
        "Analisa screenshot via vision LLM. Recebe image_path e context "
        "(ex: 'hero saas'). Retorna dict com tipografia/cores/layout/cta/padroes."
    )

    def _run(self, image_path: str, context: str) -> Dict[str, Any]:
        raw = _call_vision(image_path, context)
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": True}
