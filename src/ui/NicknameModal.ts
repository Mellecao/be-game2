const STORAGE_KEY = 'be-game-identity'
const GAME_SERVER = import.meta.env.VITE_GAME_SERVER_URL ?? 'http://localhost:8000'

export interface Identity {
  id: string
  name: string
  spriteChar: number
}

async function loginToServer(nickname: string): Promise<Identity | null> {
  try {
    const res = await fetch(`${GAME_SERVER}/api/players/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname }),
    })
    if (!res.ok) return null
    const data = await res.json() as { id: string; nickname: string; sprite_char: number }
    return { id: data.id, name: data.nickname, spriteChar: data.sprite_char }
  } catch {
    return null
  }
}

function saveLocal(identity: Identity) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(identity))
  } catch {
    // private mode ou quota — continua sem persistir
  }
}

function loadLocal(): Identity | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as Identity
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

function fallbackIdentity(name: string): Identity {
  const id = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (crypto.getRandomValues(new Uint8Array(1))[0] & 15) >> (c === 'x' ? 0 : 1)
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
      })
  return { id, name, spriteChar: Math.ceil(Math.random() * 4) }
}

export class NicknameModal {
  static async getOrPrompt(): Promise<Identity> {
    const stored = loadLocal()
    if (stored) {
      // Atualiza last_seen em background sem bloquear o boot
      loginToServer(stored.name).catch(() => {})
      return stored
    }
    return NicknameModal.prompt()
  }

  private static prompt(): Promise<Identity> {
    return new Promise((resolve) => {
      const overlay = document.createElement('div')
      overlay.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.85);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999; font-family: monospace;
      `

      const box = document.createElement('div')
      box.style.cssText = `
        background: #1a1a2e; border: 1px solid #444; border-radius: 8px;
        padding: 32px 40px; display: flex; flex-direction: column; gap: 16px;
        min-width: 280px; color: #fff;
      `

      const title = document.createElement('h2')
      title.textContent = 'Entrar na sala'
      title.style.cssText = 'margin: 0; font-size: 18px; font-weight: 600;'

      const input = document.createElement('input')
      input.type = 'text'
      input.placeholder = 'Como quer ser chamado?'
      input.maxLength = 20
      input.style.cssText = `
        background: #111; border: 1px solid #555; border-radius: 4px;
        color: #fff; font-family: monospace; font-size: 14px;
        padding: 8px 12px; outline: none;
      `

      const btn = document.createElement('button')
      btn.textContent = 'Entrar'
      btn.disabled = true
      btn.style.cssText = `
        background: #3b5bdb; border: none; border-radius: 4px;
        color: #fff; font-family: monospace; font-size: 14px;
        padding: 10px; cursor: pointer; opacity: 0.5; transition: opacity 0.2s;
      `

      const status = document.createElement('p')
      status.style.cssText = 'margin: 0; font-size: 12px; color: #888; min-height: 16px;'

      input.addEventListener('input', () => {
        const ok = input.value.trim().length > 0
        btn.disabled = !ok
        btn.style.opacity = ok ? '1' : '0.5'
        status.textContent = ''
      })

      const confirm = async () => {
        const name = input.value.trim()
        if (!name) return

        btn.disabled = true
        btn.textContent = 'Entrando...'
        status.textContent = ''

        const fromServer = await loginToServer(name)
        const identity = fromServer ?? fallbackIdentity(name)

        saveLocal(identity)
        overlay.remove()
        resolve(identity)
      }

      btn.addEventListener('click', confirm)
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirm()
      })

      box.append(title, input, btn, status)
      overlay.appendChild(box)
      document.body.appendChild(overlay)
      input.focus()
    })
  }
}
