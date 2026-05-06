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

PASSO FINAL OBRIGATÓRIO: Após concluir toda a implementação, crie um arquivo
chamado `.claude-done` nesta pasta com o conteúdo "done".
Use a ferramenta Write: path=".claude-done", content="done".
Isso é OBRIGATÓRIO — é o sinal de que você terminou.
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
                "e sem usar nenhuma skill de superpowers.\n\n"
                + prompt
                + "\n\nPASSO FINAL OBRIGATÓRIO: crie o arquivo `.claude-done` nesta pasta "
                "com conteúdo \"done\" usando a ferramenta Write."
            )
            done_event = threading.Event()
            print(f"[dev_tool] iniciando job para '{project_slug}' em {project_dir}")
            self._launch(project_dir, project_slug, full_prompt, done_event)
            print(f"[dev_tool] aguardando Claude terminar para '{project_slug}'...")
            done_event.wait()
            return (
                f"Projeto '{project_slug}' concluido!\n"
                f"Pasta: {project_dir.resolve()}"
            )
        except Exception as exc:
            print(f"[dev_tool] EXCECAO em _run para '{project_slug}': {exc}")
            return f"error: {exc}"

    def _launch(self, project_dir: Path, project_slug: str, prompt: str, done_event: threading.Event) -> None:
        proc_ref: list = [None]
        win_title = f"be-dev-{project_slug}"

        def _find_and_focus(title: str) -> bool:
            try:
                import win32gui
                import win32con
                found = []

                def _cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        if title in win32gui.GetWindowText(hwnd):
                            found.append(hwnd)

                win32gui.EnumWindows(_cb, None)
                if found:
                    hwnd = found[-1]
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    print(f"[dev_tool] foco definido: hwnd={hwnd}")
                    return True
            except Exception as e:
                print(f"[dev_tool] _find_and_focus erro: {e}")
            return False

        def _watch_sentinel() -> None:
            sentinel = project_dir / ".claude-done"
            deadline = time.monotonic() + 5400  # 90 min max
            while time.monotonic() < deadline:
                if sentinel.exists():
                    try:
                        sentinel.unlink()
                    except Exception:
                        pass
                    print(f"[dev_tool] SENTINEL detectado — '{project_slug}' concluido!")
                    done_event.set()
                    time.sleep(15)
                    proc = proc_ref[0]
                    if proc:
                        try:
                            proc.terminate()
                            print(f"[dev_tool] terminal de '{project_slug}' encerrado")
                        except Exception:
                            pass
                    return
                time.sleep(2)
            print(f"[dev_tool] TIMEOUT (90min) para '{project_slug}' — sentinel nao detectado")
            done_event.set()

        def _automate() -> None:
            print(f"[dev_tool] abrindo PowerShell com titulo '{win_title}'...")
            proc = subprocess.Popen(
                [
                    "powershell.exe", "-NoExit", "-Command",
                    f"$host.ui.rawui.windowtitle = '{win_title}'; "
                    f"Set-Location '{project_dir}'"
                ],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            proc_ref[0] = proc
            print(f"[dev_tool] processo PID={proc.pid} — aguardando janela aparecer...")

            # Aguarda a janela com o titulo unico aparecer (até 15s)
            hwnd_found = False
            for attempt in range(30):
                time.sleep(0.5)
                if _find_and_focus(win_title):
                    print(f"[dev_tool] janela encontrada na tentativa {attempt + 1}")
                    hwnd_found = True
                    break

            if not hwnd_found:
                print(f"[dev_tool] AVISO: janela nao encontrada pelo titulo — continuando mesmo assim")

            time.sleep(1.0)
            print(f"[dev_tool] digitando 'claude --dangerously-skip-permissions'...")
            pyautogui.typewrite("claude --dangerously-skip-permissions", interval=0.07)
            pyautogui.press("enter")

            print(f"[dev_tool] aguardando Claude CLI inicializar (15s)...")
            time.sleep(15)

            _find_and_focus(win_title)
            time.sleep(0.6)
            print(f"[dev_tool] pressionando '1' (confiar no diretorio)...")
            pyautogui.press("1")
            time.sleep(3)

            _find_and_focus(win_title)
            time.sleep(0.6)
            print(f"[dev_tool] colando prompt ({len(prompt)} chars)...")
            pyperclip.copy(prompt)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
            print(f"[dev_tool] prompt enviado para '{project_slug}' — aguardando .claude-done")

        threading.Thread(target=_automate, daemon=True).start()
        threading.Thread(target=_watch_sentinel, daemon=True).start()
