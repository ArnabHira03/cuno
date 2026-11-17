// The order cards appear in a hand: by colour (wilds last), then kind, then value.
import type { Card } from './types';

const COLOR_ORDER = { red: 0, yellow: 1, green: 2, blue: 3 } as const;
const KIND_ORDER = { number: 0, skip: 1, reverse: 2, draw2: 3, wild: 4, wild4: 5 } as const;

export function sortCards(cards: Card[]): Card[] {
  return [...cards].sort(
    (a, b) =>
      (a.color ? COLOR_ORDER[a.color] : 9) - (b.color ? COLOR_ORDER[b.color] : 9) ||
      KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
      (a.value ?? 0) - (b.value ?? 0) ||
      a.id - b.id,
  );
}
