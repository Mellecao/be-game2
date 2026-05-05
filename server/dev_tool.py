import subprocess
import threading
import time
from pathlib import Path

import pyautogui
import pyperclip
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

pyautogui.FAILSAFE = False

VIDEOS_DIR = Path(r"C:\Users\v27me\Videos")

_CLAUDE_MD = """\
# INSTRUÇÕES OBRIGATÓRIAS — LEIA ANTES DE QUALQUER COISA

NUNCA use skills de superpowers (brainstorming, writing-plans, executing-plans,
subagent-driven-development, verification-before-completion, ou qualquer outra skill).

NUNCA peça confirmação, aprovação ou revisão antes de implementar.

NUNCA entre em modo de planejamento (Plan Mode).

Implemente IMEDIATAMENTE e DIRETAMENTE tudo que for pedido, sem perguntas.
"""


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
        "Cria pasta em C:/Users/v27me/Videos/{project_slug}, abre um terminal PowerShell, "
        "digita 'claude --dangerously-skip-permissions', aguarda carregar, "
        "pressiona 1 para confiar no projeto, cola o prompt e pressiona Enter."
    )
    args_schema: type[BaseModel] = DevToolInput

    def _run(self, project_slug: str, prompt: str) -> str:
        try:
            project_dir = VIDEOS_DIR / project_slug
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
            full_prompt = (
                "IMPORTANTE: implemente tudo diretamente, sem pedir confirmação "
                "e sem usar nenhuma skill de superpowers.\n\n" + prompt
            )
            self._launch(project_dir, full_prompt)
            return (
                f"Pasta criada: {project_dir.resolve()}\n"
                f"Claude CLI iniciado no terminal. O site esta sendo construido."
            )
        except Exception as exc:
            return f"error: {exc}"

    def _launch(self, project_dir: Path, prompt: str) -> None:
        def _focus_pid(pid: int) -> bool:
            try:
                import win32gui
                import win32process
                import win32con

                found = []

                def _cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
                        if wpid == pid:
                            found.append(hwnd)

                win32gui.EnumWindows(_cb, None)
                if found:
                    hwnd = found[-1]
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    return True
            except Exception:
                pass
            return False

        def _automate() -> None:
            proc = subprocess.Popen(
                ["powershell.exe", "-NoExit"],
                cwd=str(project_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            time.sleep(3)
            _focus_pid(proc.pid)
            time.sleep(0.5)

            pyautogui.typewrite("claude --dangerously-skip-permissions", interval=0.05)
            pyautogui.press("enter")
            time.sleep(10)

            _focus_pid(proc.pid)
            time.sleep(0.3)
            pyautogui.press("1")
            time.sleep(2)

            _focus_pid(proc.pid)
            time.sleep(0.3)
            pyperclip.copy(prompt)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")

        threading.Thread(target=_automate, daemon=True).start()
