"""HTTP tool para Hunyuan3D-2GP em 127.0.0.1:8081."""
from __future__ import annotations

import os
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger


class Hunyuan3DTool(BaseTool):
    name: str = "hunyuan3d_generate"
    description: str = (
        "Gera um modelo 3D GLB a partir de uma imagem PNG usando o servidor "
        "Hunyuan3D-2GP local. Argumento obrigatorio: image_path (caminho absoluto "
        "do PNG). Retorna o caminho absoluto do GLB gerado."
    )
    api_url: str = Field(
        default_factory=lambda: os.environ.get("HUNYUAN_API_URL", "http://127.0.0.1:8081")
    )
    octree_resolution: int = Field(default=128)
    num_inference_steps: int = Field(default=5)
    guidance_scale: float = Field(default=5.0)
    seed: int = Field(default=1234)
    enable_texture: bool = Field(default=False)

    def _run(self, image_path: str) -> str:
        if not image_path or not Path(image_path).exists():
            return f"Erro: image_path nao existe: '{image_path}'"

        payload = {
            "image_path": image_path,
            "octree_resolution": self.octree_resolution,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "seed": self.seed,
            "enable_texture": self.enable_texture,
        }
        try:
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            return (
                f"Erro ao chamar API do Hunyuan em {self.api_url}: {e}. "
                "Verifique se o servidor esta rodando."
            )

        data = response.json()
        glb_path = data.get("path") or data.get("glb_path")
        if not glb_path:
            return f"API Hunyuan retornou sem path do GLB. Resposta: {data}"

        pipeline_logger.log_event(None, "asset_generated", {
            "agent_id": "agente_3d",
            "kind": "glb",
            "path": glb_path,
            "source_image": image_path,
        })
        return glb_path
