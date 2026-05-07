# server/flux_tool.py
import base64
import os
import threading
import time
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger

# Garante uma única request ao Forge por vez, mesmo com múltiplas threads de pipeline rodando em paralelo
_flux_lock = threading.Semaphore(1)


class FluxImageTool(BaseTool):
    name: str = "flux_image"
    description: str = (
        "Gera uma imagem a partir de um prompt EM INGLES usando Flux Schnell NF4 "
        "via API do Stable Diffusion WebUI Forge. "
        "Retorna o caminho absoluto do PNG gerado. "
        "Argumento unico: 'prompt' (string descritiva em ingles, detalhada)."
    )
    api_url: str = Field(
        default_factory=lambda: os.environ.get("FORGE_API_URL", "http://127.0.0.1:7860")
    )
    output_dir: str = Field(default="output")
    width: int = Field(default=1024)
    height: int = Field(default=1024)
    steps: int = Field(default=4)
    cfg_scale: float = Field(default=1)
    sampler_name: str = Field(default="Euler")

    def _run(self, prompt: str) -> str:
        with _flux_lock:
            return self._generate(prompt)

    def _generate(self, prompt: str) -> str:
        payload = {
            "prompt": prompt,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "width": self.width,
            "height": self.height,
            "sampler_name": self.sampler_name,
            "send_images": True,
            "save_images": False,
        }
        try:
            response = requests.post(
                f"{self.api_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            return (
                f"Erro ao chamar API do Forge em {self.api_url}: {e}. "
                "Verifique se o Forge esta rodando com --api."
            )

        data = response.json()
        if not data.get("images"):
            return (
                "API retornou resposta sem imagens. "
                "Verifique se o checkpoint Flux esta carregado no Forge."
            )

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        out_path = Path(self.output_dir) / f"flux-{timestamp}.png"
        out_path.write_bytes(base64.b64decode(data["images"][0]))
        abs_path = str(out_path.resolve())

        pipeline_logger.log_event(None, "asset_generated", {
            "agent_id": "image_artist",
            "kind": "png",
            "path": abs_path,
            "prompt": prompt[:200],
        })
        return abs_path
