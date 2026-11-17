<script lang="ts">
  // Spectators only: every other player's hand as tiny chips, in a corner of the felt.
  // Deliberately has no data-card-id / data-hand attributes, so fx flights never land here.
  import { sortCards } from './cardSort';
  import { client, storageGet, storageSet } from './client.svelte';
  import type { Card, GameView, RoomState } from './types';

  let { state: s, startCollapsed }: { state: RoomState; startCollapsed: boolean } = $props();
  const g = $derived(s.game as GameView);

  const KEY = 'cuno:handsPanel';
  const saved = storageGet(KEY);
  // The viewer's own choice wins; until they make one, follow the (live) table size.
  let choice = $state<boolean | null>(saved === null ? null : saved === '1');
  const collapsed = $derived(choice ?? startCollapsed);

  function toggle() {
    choice = !collapsed;
    storageSet(KEY, choice ? '1' : '0');
  }

  // Play order, starting with whoever plays after the followed player.
  const rows = $derived.by(() => {
    const n = s.players.length;
    const from = s.watching ?? 0;
    const step = g.direction === -1 ? n - 1 : 1;
    const out = [];
    for (let i = 1; i < n; i++) {
      const seat = (from + step * i) % n;
      out.push({ seat, name: s.players[seat].name, cards: sortCards(g.hands?.[String(seat)] ?? []) });
    }
    return out;
  });

  const SYMBOL: Record<Card['kind'], string> = { number: '', skip: '⊘', reverse: '⇄', draw2: '+2', wild: 'W', wild4: '+4' };
  const label = (c: Card) => (c.kind === 'number' ? String(c.value) : SYMBOL[c.kind]);
  const title = (c: Card) =>
    c.kind === 'wild' ? 'Wild' : c.kind === 'wild4' ? 'Wild Draw Four' : `${c.color} ${c.kind === 'number' ? c.value : c.kind}`;
</script>

<div class="panel-hands" class:collapsed>
  <button class="head" onclick={toggle} aria-expanded={!collapsed}>
    <span>Hands</span><span aria-hidden="true">{collapsed ? '▴' : '–'}</span>
  </button>
  {#if !collapsed}
    <ul class="rows">
      {#each rows as r (r.seat)}
        <li>
          <button class="row" class:now={g.phase === 'playing' && g.turn === r.seat} onclick={() => client.watch(r.seat)} title="Watch {r.name}">
            <span class="who">{r.name}</span>
            <span class="chips">
              {#each r.cards as c (c.id)}
                <span class="c {c.color ?? 'wild'}" title={title(c)}>{label(c)}</span>
              {/each}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .panel-hands {
    position: absolute;
    left: 10px;
    bottom: 10px;
    z-index: 6;
    width: min(260px, 60%);
    max-height: 40%;
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    border: 1px solid var(--border);
    border-radius: 12px;
    backdrop-filter: blur(6px);
    box-shadow: var(--shadow);
    color: var(--text);
    font-size: 0.75rem;
  }

  .panel-hands.collapsed {
    width: auto;
  }

  .head {
    all: unset;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 6px 10px;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-dim);
  }

  .head:focus-visible,
  .row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
    border-radius: 8px;
  }

  .rows {
    list-style: none;
    margin: 0;
    padding: 0 4px 4px;
    overflow-y: auto;
    min-height: 0;
  }

  .row {
    all: unset;
    box-sizing: border-box;
    cursor: pointer;
    width: 100%;
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 3px 6px;
    border-radius: 8px;
  }

  .row:hover {
    background: var(--surface);
  }

  .row.now {
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }

  .who {
    flex: none;
    width: 52px;
    padding-top: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
  }

  .c {
    min-width: 16px;
    height: 20px;
    padding: 0 2px;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.5);
    font: 700 0.62rem var(--font-display);
    color: #fff;
  }

  .c.red {
    background: var(--c-red);
  }
  .c.yellow {
    background: var(--c-yellow);
    color: #1b1400;
  }
  .c.green {
    background: var(--c-green);
  }
  .c.blue {
    background: var(--c-blue);
  }
  .c.wild {
    background: conic-gradient(var(--c-red) 0 25%, var(--c-yellow) 0 50%, var(--c-green) 0 75%, var(--c-blue) 0);
    text-shadow: 0 0 2px #000;
  }
</style>
