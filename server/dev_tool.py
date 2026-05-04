import subprocess
import time
from pathlib import Path

import pyautogui
import pyperclip
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    import pygetwindow as gw
    _HAS_GW = True
except ImportError:
    _HAS_GW = False

VIDEOS_DIR = Path(r"C:\Users\v27me\Videos")


class DevToolInput(BaseModel):
    project_slug: str = Field(
        ...,
        description="Nome curto do projeto em kebab-case, ex: rose-beauty ou cafe-central",
    )
    prompt: str = Field(
        ...,
        description="Prompt completo para o Claude CLI construir o site",
    )


class OpenClaudeCliTool(BaseTool):
    name: str = "open_claude_cli"
    description: str = (
        "Cria pasta em C:/Users/v27me/Videos/{project_slug}, abre Open Interpreter "
        "que abre um terminal PowerShell, digita 'claude', aguarda 15s, pressiona 1 "
        "para confiar no projeto e cola o prompt de desenvolvimento. "
        "Retorna o caminho absoluto da pasta criada."
    )
    args_schema: type[BaseModel] = DevToolInput

    def _run(self, project_slug: str, prompt: str) -> str:
        try:
            project_dir = VIDEOS_DIR / project_slug
            project_dir.mkdir(parents=True, exist_ok=True)
            self._launch(project_dir, prompt)
            return (
                f"Pasta criada: {project_dir.resolve()}\n"
                f"Claude CLI iniciado no terminal. O site está sendo construído."
            )
        except Exception as exc:
            return f"error: {exc}"

    def _launch(self, project_dir: Path, prompt: str) -> None:
        from interpreter import interpreter as oi

        oi.auto_run = True
        oi.llm.model = "ollama/gemma4:e4b"
        oi.llm.api_base = "http://127.0.0.1:11434"
        oi.llm.context_window = 8096

        escaped_dir = str(project_dir).replace("\\", "\\\\")
        prompt_var = repr(prompt)

        script = f"""
import subprocess, time, pyautogui, pyperclip
pyautogui.FAILSAFE = False

subprocess.Popen(
    ['powershell.exe', '-NoExit'],
    cwd=r'{escaped_dir}',
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)
time.sleep(2)

try:
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle('Windows PowerShell') + gw.getWindowsWithTitle('powershell')
    if wins:
        wins[-1].activate()
        time.sleep(0.5)
except Exception:
    pass

pyautogui.typewrite('claude', interval=0.05)
pyautogui.press('enter')
time.sleep(15)

pyautogui.typewrite('1', interval=0.05)
pyautogui.press('enter')
time.sleep(1)

prompt = {prompt_var}
pyperclip.copy(prompt)
pyautogui.hotkey('ctrl', 'v')
pyautogui.press('enter')
print('Prompt enviado ao Claude CLI.')
"""

        oi.chat(
            f"Execute este script Python exatamente como está, sem modificações:\n\n```python\n{script}\n```"
        )
