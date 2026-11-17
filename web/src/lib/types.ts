// Mirrors src/cuno/protocol.py, views.py and rooms.py. Change both sides together.

export type Color = 'red' | 'yellow' | 'green' | 'blue';
export type Kind = 'number' | 'skip' | 'reverse' | 'draw2' | 'wild' | 'wild4';

export interface Card {
  id: number;
  kind: Kind;
  color: Color | null;
  value: number | null;
}

export type Pending =
  | { type: 'challenge'; player: number; victim: number }
  | { type: 'choose_color'; seat: number };

export interface LastRound {
  winner: number;
  points: number;
  breakdown: Record<string, number>;
  hands: Record<string, Card[]>;
}

export interface GameView {
  phase: 'playing' | 'round_over' | 'game_over';
  round: number;
  dealer: number;
  hand: Card[];
  hand_counts: number[];
  top: Card | null;
  discard_count: number;
  draw_count: number;
  current_color: Color | null;
  direction: 1 | -1;
  turn: number;
  actor: number | null;
  pending: Pending | null;
  drawn_card_id: number | null;
  playable: number[];
  uno_called: boolean[];
  uno_vulnerable: number | null;
  scores: number[];
  target_score: number;
  last_round: LastRound | null;
  /** Spectators only: every player's hand, keyed by seat. */
  hands?: Record<string, Card[]>;
}

export interface PlayerInfo {
  seat: number;
  name: string;
  connected: boolean;
}

export interface RoomState {
  code: string;
  version: number;
  phase: 'lobby' | GameView['phase'];
  role: 'player' | 'spectator';
  /** Your seat; null for spectators. */
  you: number | null;
  /** The seat a spectator follows; null for players. */
  watching: number | null;
  /** Names of connected spectators. */
  spectators: string[];
  host: number | null;
  players: PlayerInfo[];
  turn_seconds: number;
  time_left_ms: number | null; // turn time left when this snapshot was sent
  game: GameView | null;
}

/** The seat the table is drawn around: your own, or the one a spectator follows. */
export function viewSeat(s: RoomState): number {
  return s.you ?? s.watching ?? 0;
}

export type GameEvent = { type: string; seat?: number; [k: string]: any };

export type ServerMessage =
  | { type: 'welcome'; seat: number | null; token: string; role: 'player' | 'spectator' }
  | { type: 'state'; state: RoomState; events: GameEvent[] }
  | { type: 'error'; code: string; message: string };

export type ClientMessage =
  | { type: 'join'; name: string; token?: string | null }
  | { type: 'start' }
  | { type: 'next_round' }
  | { type: 'new_game' }
  | { type: 'leave' }
  | { type: 'play'; card_id: number; color?: Color }
  | { type: 'draw' }
  | { type: 'keep' }
  | { type: 'choose_color'; color: Color }
  | { type: 'challenge' }
  | { type: 'accept' }
  | { type: 'call_uno' }
  | { type: 'catch'; target: number }
  | { type: 'watch'; seat: number };
