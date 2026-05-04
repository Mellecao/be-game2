import { createClient, SupabaseClient, RealtimeChannel } from '@supabase/supabase-js'

export type RemotePlayerData = { id: string; name: string; spriteChar: number }
type PresenceMeta = { name: string; spriteChar: number }

export class MultiplayerService {
  onPlayerJoined: ((data: RemotePlayerData) => void) | null = null
  onPlayerLeft: ((id: string) => void) | null = null
  onPlayerMoved: ((id: string, col: number, row: number, dir: string) => void) | null = null

  private supabase: SupabaseClient
  private channel: RealtimeChannel | null = null
  private myId = ''
  private pendingPos: { col: number; row: number; dir: string } | null = null
  private intervalId: ReturnType<typeof setInterval> | null = null

  constructor() {
    this.supabase = createClient(
      import.meta.env.VITE_SUPABASE_URL as string,
      import.meta.env.VITE_SUPABASE_ANON_KEY as string
    )
  }

  async connect(playerId: string, name: string, spriteChar: number): Promise<void> {
    this.myId = playerId

    if (this.channel !== null) {
      console.warn('[MultiplayerService] connect() called while already connected — ignoring')
      return
    }

    this.channel = this.supabase.channel('room:main', {
      config: { presence: { key: playerId } },
    })

    this.channel
      .on<PresenceMeta>('presence', { event: 'join' }, ({ key, newPresences }) => {
        if (key === this.myId) return
        const p = newPresences[0]
        this.onPlayerJoined?.({ id: key, name: p.name, spriteChar: p.spriteChar })
      })
      .on('presence', { event: 'leave' }, ({ key }) => {
        if (key === this.myId) return
        this.onPlayerLeft?.(key)
      })
      .on('broadcast', { event: 'player-move' }, ({ payload }) => {
        if (payload.id === this.myId) return
        this.onPlayerMoved?.(payload.id, payload.col, payload.row, payload.dir)
      })

    await new Promise<void>((resolve, reject) => {
      this.channel!.subscribe(async (status, err) => {
        if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
          console.error('[MultiplayerService] subscription failed', status, err)
          reject(new Error(`Subscription failed: ${status}`))
          return
        }
        if (status !== 'SUBSCRIBED') return
        await this.channel!.track({ name, spriteChar })

        // Announce players already present in the room
        const state = this.channel!.presenceState<PresenceMeta>()
        for (const [key, presences] of Object.entries(state)) {
          if (key === playerId) continue
          const p = presences[0]
          this.onPlayerJoined?.({ id: key, name: p.name, spriteChar: p.spriteChar })
        }
        resolve()
      })
    })

    this.intervalId = setInterval(() => {
      if (!this.pendingPos || !this.channel) return
      this.channel.send({
        type: 'broadcast',
        event: 'player-move',
        payload: { id: this.myId, ...this.pendingPos },
      })
      this.pendingPos = null
    }, 50)
  }

  sendPosition(col: number, row: number, dir: string): void {
    this.pendingPos = { col, row, dir }
  }

  disconnect(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
    if (this.channel) this.supabase.removeChannel(this.channel)
    this.channel = null
  }
}
