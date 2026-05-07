export class PlayerChatInput {
  private el: HTMLDivElement;
  private input: HTMLInputElement;
  private listeners: { onSubmit: (text: string) => void };

  constructor(opts: { onSubmit: (text: string) => void }) {
    this.listeners = opts;

    this.el = document.createElement('div');
    this.el.id = 'player-chat-input';
    this.el.classList.add('hidden');
    this.el.innerHTML = `<input type="text" placeholder="Pergunte ao Secretário..." maxlength="500" />`;
    document.body.appendChild(this.el);

    this.input = this.el.querySelector('input')!;
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const text = this.input.value.trim();
        if (text) this.listeners.onSubmit(text);
        this._close();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this._close();
      }
    });
  }

  toggle(): void {
    if (this.el.classList.contains('hidden')) this._open();
    else this._close();
  }

  isOpen(): boolean {
    return !this.el.classList.contains('hidden');
  }

  hasFocus(): boolean {
    return document.activeElement === this.input;
  }

  private _open(): void {
    this.el.classList.remove('hidden');
    this.input.value = '';
    this.input.focus();
  }

  private _close(): void {
    this.el.classList.add('hidden');
    this.input.value = '';
    this.input.blur();
  }
}
