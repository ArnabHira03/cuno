// WebSocket connection + latest room snapshot. Components render from `client.state`.
import { tick } from 'svelte';
import type { ClientMessage, GameEvent, RoomState, ServerMessage } from './types';

const SEQUENCED = new Set(['play', 'draw', 'keep', 'choose_color', 'challenge', 'accept']);
// Errors after which reconnecting is pointless.
const FATAL = new Set(['not_found', 'in_progress', 'full', 'bad_name', 'replaced', 'not_joined']);

export type Status = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface StateHooks {
  /** Called with the new events before the new state is rendered. */
  before(events: GameEvent[], prev: RoomState | null, next: RoomState): void;
  /** Called after the DOM reflects the new state. */
  after(events: GameEvent[], prev: RoomState | null, next: RoomState): void;
}

const tokenKey = (code: string) => `cuno:token:${code}`;

export function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function storageSet(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode etc. */
  }
}

class Client {
  state = $state<RoomState | null>(null);
  status = $state<Status>('idle');
  error = $state<{ code: string; message: string } | null>(null);
  code = $state<string | null>(null);
  /** Local clock time (ms) when the current turn times out. */
  deadline = $state<number | null>(null);

  hooks: StateHooks | null = null;
  private ws: WebSocket | null = null;
  private name = '';
  private attempts = 0;
  private retryTimer: number | null = null;
  private stopped = true;
  private chain: Promise<void> = Promise.resolve();

  connect(code: string, name: string) {
    this.disconnect();
    this.code = code.toUpperCase();
    this.name = name;
    this.stopped = false;
    this.attempts = 0;
    this.error = null;
    this.open();
  }

  private open() {
    if (!this.code) return;
    this.status = this.attempts === 0 ? 'connecting' : 'reconnecting';
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/${this.code}`);
    this.ws = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'join', name: this.name, token: storageGet(tokenKey(this.code!)) }));
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data) as ServerMessage;
      // Process strictly in order so animation hooks never interleave.
      this.chain = this.chain.then(() => this.receive(msg)).catch((err) => console.error(err));
    };
    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (this.stopped) {
        this.status = 'closed';
        return;
      }
      this.status = 'reconnecting';
      const delay = Math.min(8000, 500 * 2 ** this.attempts++);
      this.retryTimer = window.setTimeout(() => this.open(), delay);
    };
  }

  private async receive(msg: ServerMessage) {
    switch (msg.type) {
      case 'welcome':
        storageSet(tokenKey(this.code!), msg.token);
        this.status = 'open';
        this.attempts = 0;
        this.error = null;
        break;
      case 'error':
        if (FATAL.has(msg.code)) {
          this.stopped = true;
          if (msg.code !== 'replaced') storageSet(tokenKey(this.code!), null);
        }
        this.error = { code: msg.code, message: msg.message };
        break;
      case 'state': {
        const prev = this.state;
        this.hooks?.before(msg.events, prev, msg.state);
        this.deadline = msg.state.time_left_ms === null ? null : Date.now() + msg.state.time_left_ms;
        this.state = msg.state;
        await tick();
        this.hooks?.after(msg.events, prev, msg.state);
        break;
      }
    }
  }

  send(msg: ClientMessage) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const out: Record<string, unknown> = { ...msg };
    if (SEQUENCED.has(msg.type)) out.seq = this.state?.version;
    this.ws.send(JSON.stringify(out));
  }

  leave() {
    if (this.code) storageSet(tokenKey(this.code), null);
    this.send({ type: 'leave' });
    this.disconnect();
    this.state = null;
    this.code = null;
    this.status = 'idle';
  }

  private disconnect() {
    this.stopped = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    const ws = this.ws;
    this.ws = null;
    ws?.close();
  }
}

export const client = new Client();
