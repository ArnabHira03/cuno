// Event-driven animations. The server sends `events` with every snapshot;
// we turn them into card flights, seat effects and toasts. If anything is
// missing (reconnect, reduced motion) the snapshot simply renders as-is.
import { mount, unmount } from 'svelte';
import Card from './Card.svelte';
import { viewSeat, type Card as CardT, type GameEvent, type RoomState } from './types';

export interface SeatEffect {
  kind: 'plus' | 'skip' | 'uno' | 'shake' | 'timeout';
  text?: string;
  key: number;
}

export interface Toast {
  id: number;
  text: string;
  tone: 'info' | 'good' | 'bad';
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
let uid = 0;

class Fx {
  hiddenHand = $state<number[]>([]);
  hiddenTop = $state<number | null>(null);
  effects = $state<Record<number, SeatEffect>>({});
  toasts = $state<Toast[]>([]);
  layer: HTMLElement | null = null;

  private captured = new Map<number, DOMRect>();

  get reduced() {
    return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // ------------------------------------------------------------ public hooks

  /** A spectator switched players: the bottom hand is a different hand now. */
  resetHand() {
    this.captured.clear();
    this.hiddenHand = [];
  }

  before(events: GameEvent[], prev: RoomState | null, next: RoomState) {
    this.captured.clear();
    document.querySelectorAll<HTMLElement>('[data-hand] [data-card-id]').forEach((el) => {
      this.captured.set(Number(el.dataset.cardId), el.getBoundingClientRect());
    });
    if (!prev?.game || !next.game || this.reduced) return;
    const plays = events.filter((e) => e.type === 'play');
    if (plays.length) this.hiddenTop = plays[plays.length - 1].card.id;
    for (const e of events) {
      if (e.type === 'draw' && e.private?.card_ids) this.hiddenHand = [...this.hiddenHand, ...e.private.card_ids];
    }
  }

  after(events: GameEvent[], prev: RoomState | null, next: RoomState) {
    // Safety net: whatever happens, un-hide this batch's cards once its flights are surely done.
    const top = this.hiddenTop;
    const hand = new Set(this.hiddenHand);
    void this.run(events, prev, next).finally(() =>
      setTimeout(() => {
        if (this.hiddenTop === top) this.hiddenTop = null;
        this.hiddenHand = this.hiddenHand.filter((id) => !hand.has(id));
      }, 900),
    );
  }

  toast(text: string, tone: Toast['tone'] = 'info', ms = 3200) {
    const t = { id: ++uid, text, tone };
    this.toasts = [...this.toasts.slice(-3), t];
    setTimeout(() => (this.toasts = this.toasts.filter((x) => x.id !== t.id)), ms);
  }

  // ---------------------------------------------------------------- internals

  private effect(seat: number, kind: SeatEffect['kind'], text?: string) {
    const key = ++uid;
    this.effects = { ...this.effects, [seat]: { kind, text, key } };
    setTimeout(() => {
      if (this.effects[seat]?.key === key) {
        const { [seat]: _, ...rest } = this.effects;
        this.effects = rest;
      }
    }, 1500);
  }

  private async run(events: GameEvent[], prev: RoomState | null, next: RoomState) {
    // `me` is the seat the table is drawn around (anchors, hand flights); `self` is your own seat,
    // null for spectators, and decides when the wording says "you".
    const me = viewSeat(next);
    const self = next.you;
    const name = (seat: number | undefined) =>
      seat === self ? 'You' : (next.players[seat ?? -1]?.name ?? 'Someone');
    const animate = !!prev?.game && !!next.game && !this.reduced;

    for (const e of events) {
      switch (e.type) {
        case 'rejoined':
          if (e.seat !== self && next.phase !== 'lobby') this.toast(`${name(e.seat)} is back`, 'good');
          break;
        case 'disconnected':
          this.toast(`${name(e.seat)} lost connection`, 'bad');
          break;
        case 'left':
          if (next.phase !== 'lobby') this.toast(`${prev?.players[e.seat ?? -1]?.name ?? 'Someone'} left`);
          break;
        case 'deal':
          if (!this.reduced) await this.dealAnimation(next);
          break;
        case 'play': {
          if (!animate) break;
          const from = e.seat === me ? this.captured.get(e.card.id) : this.seatRect(e.seat);
          const to = this.rect('[data-pile="discard"]');
          if (from && to) {
            const done = this.fly(e.card, from, to, { duration: 380, spin: (Math.random() - 0.5) * 30 });
            await sleep(240);
            void done.then(() => {
              if (this.hiddenTop === e.card.id) this.hiddenTop = null;
            });
          } else if (this.hiddenTop === e.card.id) this.hiddenTop = null;
          break;
        }
        case 'draw': {
          if (['draw2', 'wild4', 'challenge_guilty', 'challenge_failed', 'uno_penalty'].includes(e.reason)) {
            this.effect(e.seat!, 'plus', `+${e.count}`);
          }
          if (!animate || !e.count) break;
          const from = this.rect('[data-pile="draw"]');
          if (!from) break;
          if (e.private?.card_ids) {
            const ids: number[] = e.private.card_ids;
            const flights = ids.map(async (id, i) => {
              await sleep(i * 90);
              const to = this.rect(`[data-hand] [data-card-id="${id}"]`);
              if (to) await this.fly(null, from, to, { duration: 420 });
              this.hiddenHand = this.hiddenHand.filter((x) => x !== id);
            });
            await sleep(Math.min(ids.length, 4) * 90 + 120);
            void Promise.all(flights);
          } else {
            const to = this.seatRect(e.seat);
            if (!to) break;
            for (let i = 0; i < Math.min(e.count, 4); i++) {
              void this.fly(null, from, to, { duration: 420, delay: i * 90, endScale: 0.4 });
            }
            await sleep(Math.min(e.count, 4) * 90 + 120);
          }
          break;
        }
        case 'skip':
          this.effect(e.seat!, 'skip');
          if (e.seat === self) this.toast('You were skipped', 'bad');
          break;
        case 'reverse':
          this.toast('Direction reversed ⟲');
          break;
        case 'uno':
          this.effect(e.seat!, 'uno', 'CUNO!');
          break;
        case 'catch':
          this.effect(e.target, 'shake');
          this.toast(
            e.target === self
              ? `${name(e.seat)} caught you — draw 2!`
              : `${name(e.seat)} caught ${name(e.target)} not calling CUNO! +2`,
            e.target === self ? 'bad' : 'good',
          );
          break;
        case 'challenge': {
          const guilty = e.result === 'guilty';
          this.toast(
            `${name(e.seat)} challenged ${name(e.target)} — ${guilty ? 'bluff caught! +4' : 'it was legal. +6'}`,
            guilty ? 'good' : 'bad',
            4500,
          );
          break;
        }
        case 'accept':
          break;
        case 'color_chosen':
          if (e.seat !== self) this.toast(`${name(e.seat)} chose ${e.color}`);
          break;
        case 'timeout':
          this.effect(e.seat!, 'timeout');
          this.toast(e.seat === self ? 'Time ran out — you drew a card' : `${name(e.seat)} ran out of time`);
          break;
        case 'reshuffle':
          this.toast('Discard pile reshuffled into the deck');
          break;
      }
    }
  }

  private rect(selector: string): DOMRect | null {
    return document.querySelector(selector)?.getBoundingClientRect() ?? null;
  }

  private seatRect(seat: number | undefined): DOMRect | null {
    return this.rect(`[data-seat-anchor="${seat}"]`);
  }

  private async dealAnimation(next: RoomState) {
    const from = this.rect('[data-pile="draw"]');
    if (!from || !next.game) return;
    const n = next.players.length;
    for (let round = 0; round < 2; round++) {
      for (let s = 0; s < n; s++) {
        const to = this.seatRect(s);
        if (to) void this.fly(null, from, to, { duration: 360, endScale: s === viewSeat(next) ? 0.9 : 0.4 });
        await sleep(45);
      }
    }
  }

  /** Fly a card (or a card back) from one rect to another. */
  private async fly(
    card: CardT | null,
    from: DOMRect,
    to: DOMRect,
    opts: { duration?: number; delay?: number; spin?: number; endScale?: number } = {},
  ) {
    if (!this.layer) return;
    const host = document.createElement('div');
    host.className = 'flight';
    this.layer.appendChild(host);
    const comp = mount(Card, { target: host, props: { card, size: 'md' } });
    const own = host.getBoundingClientRect();
    const w = own.width || 86;
    const h = own.height || 129;
    // Position the flight at the destination's centre; animate from the source.
    host.style.left = `${to.left + to.width / 2 - w / 2}px`;
    host.style.top = `${to.top + to.height / 2 - h / 2}px`;
    const dx = from.left + from.width / 2 - (to.left + to.width / 2);
    const dy = from.top + from.height / 2 - (to.top + to.height / 2);
    const s0 = Math.max(0.25, Math.min(from.width / w, 1.3));
    const s1 = opts.endScale ?? Math.max(0.25, Math.min(to.width / w, 1.3));
    const spin = opts.spin ?? 0;
    const anim = host.animate(
      [
        { transform: `translate(${dx}px, ${dy}px) scale(${s0}) rotate(0deg)`, opacity: 1 },
        {
          transform: `translate(${dx * 0.45}px, ${dy * 0.45 - 30}px) scale(${(s0 + s1) / 2 + 0.08}) rotate(${spin / 2}deg)`,
          opacity: 1,
          offset: 0.5,
        },
        { transform: `translate(0, 0) scale(${s1}) rotate(${spin}deg)`, opacity: opts.endScale ? 0 : 1 },
      ],
      {
        duration: opts.duration ?? 400,
        delay: opts.delay ?? 0,
        easing: 'cubic-bezier(0.3, 0.7, 0.2, 1)',
        fill: 'both',
      },
    );
    try {
      await anim.finished;
    } catch {
      /* cancelled */
    }
    unmount(comp);
    host.remove();
  }
}

export const fx = new Fx();
