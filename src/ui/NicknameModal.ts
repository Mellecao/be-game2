const STORAGE_KEY = 'be-game-identity'

export interface Identity {
  id: string
  name: string
  spriteChar: number
}

export class NicknameModal {
  static async getOrPrompt(): Promise<Identity> {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        return JSON.parse(stored) as Identity
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
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

      input.addEventListener('input', () => {
        const ok = input.value.trim().length > 0
        btn.disabled = !ok
        btn.style.opacity = ok ? '1' : '0.5'
      })

      const confirm = () => {
        const name = input.value.trim()
        if (!name) return
        const identity: Identity = {
          id: crypto.randomUUID(),
          name,
          spriteChar: Math.ceil(Math.random() * 4),
        }
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(identity))
        } catch {
          // Storage unavailable (private mode, quota). Game continues without persisting.
        }
        overlay.remove()
        resolve(identity)
      }

      btn.addEventListener('click', confirm)
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirm()
      })

      box.append(title, input, btn)
      overlay.appendChild(box)
      document.body.appendChild(overlay)
      input.focus()
    })
  }
}
