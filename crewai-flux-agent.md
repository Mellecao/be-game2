# Instruções: Adicionar Agente de Geração de Imagens (Flux) ao Projeto CrewAI

> Documento de spec para um agente executor. Siga as etapas em ordem. Não improvise nomes ou caminhos — eles devem casar com o que já existe no projeto.

## 1. Objetivo

Adicionar ao **pacote `server/`** do projeto CrewAI em `C:\Users\v27me\Videos\be-game\` um novo agente capaz de gerar imagens via **Flux Schnell NF4 v2**, usando como backend a **API do Stable Diffusion WebUI Forge** (já instalado em `./stable-diffusion-webui-forge/`).

Resultado esperado: existe uma factory `create_image_artist()` em `server/agents.py` e uma task `create_image_generation_task()` em `server/tasks.py` que, juntas, geram um PNG em `output/` a partir de uma descrição em português.

## 2. Pré-requisitos (verificar antes de começar)

1. Modelo já está em `stable-diffusion-webui-forge/models/Stable-diffusion/flux1-schnell-nf4-v2/flux1-schnell-bnb-nf4-v2.safetensors` (12 GB). **Não baixe de novo.**
2. Forge precisa rodar com `--api`. Edite `stable-diffusion-webui-forge/webui-user.bat` e garanta que `COMMANDLINE_ARGS` contenha `--api`. Exemplo:
   ```
   set COMMANDLINE_ARGS=--api
   ```
3. Forge ativo em `http://127.0.0.1:7860`. Teste:
   ```powershell
   curl http://127.0.0.1:7860/sdapi/v1/sd-models
   ```
   Deve retornar JSON listando o checkpoint Flux.
4. Variável `OPENROUTER_API_KEY` definida (já é usada por `server/agents.py`).
5. `requirements.txt` já tem `crewai>=1.14.0`. **Não adicione bibliotecas novas** — `requests` é transitivo via crewai.

## 3. Contexto do projeto (padrões existentes — respeitar à risca)

- **Localização**: o projeto real é o **pacote `server/`** (tem `__init__.py`). Os arquivos `agents.py`, `tasks.py`, `trello_tool.py` na **raiz são legado** — **NÃO mexa neles**.
- **Imports**: dentro de `server/`, use **imports relativos** (`from .flux_tool import FluxImageTool`).
- **LLM**: definido em `server/agents.py` como:
  ```python
  llm = LLM(
      model="openrouter/deepseek/deepseek-v4-flash",
      base_url="https://openrouter.ai/api/v1",
      api_key=os.environ.get("OPENROUTER_API_KEY", ""),
      stream=True,
  )
  ```
  **Reutilize** esse `llm` — não crie outro.
- **Padrão de Agent**: `verbose=False`, `allow_delegation=False`, `role/goal/backstory` em PT-BR sem acentos especiais que possam quebrar (siga o estilo dos agentes existentes — eles usam "voce", "portugues", "informacao" sem acentos).
- **Padrão de Tool**: herda de `crewai.tools.BaseTool`, usa `pydantic.Field(default_factory=...)` para configuração via env. `_run` retorna **string**.
- **Padrão de Task**: `description` recebe o input do usuário interpolado, `expected_output` em uma frase, `agent` injetado. Tudo em PT-BR.

## 4. Arquivos a criar / modificar

### 4.1 `server/flux_tool.py` (novo)

```python
import base64
import os
import time
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import Field


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
    steps: int = Field(default=4)        # Schnell: 4 passos e o sweet spot
    cfg_scale: float = Field(default=1)  # Schnell foi treinado com CFG=1
    sampler_name: str = Field(default="Euler")

    def _run(self, prompt: str) -> str:
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
        return str(out_path.resolve())
```

**Decisões importantes** (não mude sem motivo):
- `steps=4`, `cfg_scale=1`: Schnell é destilado, valores maiores degradam.
- `send_images=True, save_images=False`: queremos os bytes na resposta, não que o Forge salve em pasta dele.
- Timeout 600s: primeira chamada carrega o modelo (~30s), gerações posteriores são rápidas.

### 4.2 Modificar `server/agents.py` — adicionar ao final

```python
from .flux_tool import FluxImageTool


def create_image_artist() -> Agent:
    return Agent(
        role="Artista Visual de IA",
        goal=(
            "Transformar descricoes em portugues em prompts detalhados em ingles "
            "e gerar imagens de alta qualidade usando Flux Schnell via flux_image."
        ),
        backstory=(
            "Voce e um artista visual da Black Elephant especializado em direcionar "
            "modelos de difusao. Domina vocabulario fotografico e artistico em ingles "
            "(lente, iluminacao, composicao, estilo). Sempre traduz o pedido do usuario "
            "(que vem em portugues) para um prompt rico em ingles ANTES de chamar a "
            "ferramenta flux_image. Ao final, reporta em portugues brasileiro qual foi "
            "o prompt usado e o caminho do PNG gerado."
        ),
        tools=[FluxImageTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
```

### 4.3 Modificar `server/tasks.py` — adicionar ao final

```python
def create_image_generation_task(agent: Agent, descricao: str) -> Task:
    return Task(
        description=(
            f"O usuario pediu uma imagem com a seguinte descricao (em portugues):\n\n"
            f"\"{descricao}\"\n\n"
            f"Passos obrigatorios:\n"
            f"1. Reescreva a descricao como um prompt detalhado em INGLES, "
            f"   com no minimo 30 palavras, incluindo: assunto, estilo visual, "
            f"   iluminacao, composicao e qualidade (ex: 'cinematic', '8k', "
            f"   'sharp focus').\n"
            f"2. Chame a ferramenta 'flux_image' passando esse prompt.\n"
            f"3. Aguarde o caminho do arquivo retornado.\n"
            f"4. Responda em portugues brasileiro com:\n"
            f"   - O prompt em ingles que voce criou\n"
            f"   - O caminho do PNG gerado"
        ),
        expected_output=(
            "Resposta em portugues contendo o prompt em ingles utilizado e o caminho "
            "absoluto do PNG gerado pela ferramenta flux_image."
        ),
        agent=agent,
    )
```

### 4.4 Expor via API (opcional, só se houver pedido explícito)

O `server/api.py` já é o entry point FastAPI do projeto. **NÃO crie endpoint novo agora** — deixe o agente acessível apenas via import nos testes/pipeline, igual aos outros. Adicionar ao FastAPI deve ser feito em PR separado se requisitado.

## 5. Testes

Existe `tests/test_pipeline.py`. **Adicione um teste mínimo** em `tests/test_flux_tool.py`:

```python
import os
from unittest.mock import patch, MagicMock
import base64
from server.flux_tool import FluxImageTool


def test_flux_tool_saves_png(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_API_URL", "http://fake-forge")
    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()
    fake_response = MagicMock()
    fake_response.json.return_value = {"images": [fake_png_b64]}
    fake_response.raise_for_status.return_value = None

    tool = FluxImageTool(output_dir=str(tmp_path))
    with patch("server.flux_tool.requests.post", return_value=fake_response):
        result = tool._run("a cat in space")

    assert result.endswith(".png")
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0


def test_flux_tool_handles_api_error(tmp_path):
    import requests as r
    tool = FluxImageTool(api_url="http://127.0.0.1:1", output_dir=str(tmp_path))
    with patch(
        "server.flux_tool.requests.post",
        side_effect=r.ConnectionError("refused"),
    ):
        result = tool._run("anything")
    assert "Erro ao chamar API do Forge" in result
```

Rode: `pytest tests/test_flux_tool.py -v`. Ambos devem passar.

## 6. Verificação manual (executor DEVE rodar antes de declarar pronto)

1. Forge rodando com `--api`:
   ```powershell
   curl http://127.0.0.1:7860/sdapi/v1/sd-models
   ```
2. Teste o agente em um REPL ou script descartável:
   ```python
   from server.agents import create_image_artist
   from server.tasks import create_image_generation_task
   from crewai import Crew

   artist = create_image_artist()
   task = create_image_generation_task(
       artist, "um gato astronauta flutuando perto de Saturno, estilo cinematografico"
   )
   crew = Crew(agents=[artist], tasks=[task], verbose=True)
   print(crew.kickoff())
   ```
3. **Critérios de sucesso:**
   - Sem traceback.
   - Existe arquivo novo `output/flux-YYYYMMDD-HHMMSS.png` com tamanho > 100 KB.
   - Saída final do CrewAI menciona o prompt em inglês e o caminho do arquivo.

Falhou? Investigue antes de mexer em código:
- API offline → erro de conexão na tool.
- Checkpoint não carregado no Forge → resposta sem imagens.
- OpenRouter sem chave / sem crédito → CrewAI trava antes de chamar a tool.

## 7. Restrições (NÃO faça)

- ❌ Não toque em `agents.py`, `tasks.py`, `trello_tool.py` na **raiz** — são legado.
- ❌ Não troque o LLM. Reutilize `llm` de `server/agents.py`.
- ❌ Não crie um segundo objeto `LLM` apontando para outro provider.
- ❌ Não adicione `diffusers`, `torch`, ou outras libs pesadas — integração é via API HTTP.
- ❌ Não retorne base64 da tool. Salve em disco e retorne o caminho.
- ❌ Não escreva inglês em `description` / `goal` / `backstory` — o pacote inteiro é PT-BR (sem acentos especiais nos campos do CrewAI, igual ao padrão atual).
- ❌ Não modifique `stable-diffusion-webui-forge/` exceto, se necessário, `webui-user.bat` para adicionar `--api`.
- ❌ Não adicione endpoint no `server/api.py` sem pedido explícito.
- ❌ Não crie pastas novas — apenas arquivos dentro de `server/` e `tests/`.

## 8. Extensão futura (fora do escopo)

Não implementar agora:
- Endpoint FastAPI em `server/api.py` para gerar via HTTP.
- Integrar com o pipeline Trello: ler card → gerar imagem → anexar ao card via `update_card_description`.
- `img2img` para refinamento iterativo.
- Cache de imagens por prompt.

Mantenha o escopo estritamente nas seções 4, 5 e 6.
