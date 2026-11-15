<script lang="ts">
  import { flip } from 'svelte/animate';
  import { fly } from 'svelte/transition';
  import Card from './Card.svelte';
  import type { Card as CardT } from './types';

  let {
    cards,
    playable,
    hidden,
    myTurn,
    selected = null,
    onplay,
  }: {
    cards: CardT[];
    playable: number[];
    hidden: number[];
    myTurn: boolean;
    selected?: number | null;
    onplay: (card: CardT) => void;
  } = $props();

  const COLOR_ORDER = { red: 0, yellow: 1, green: 2, blue: 3 } as const;
  const KIND_ORDER = { number: 0, skip: 1, reverse: 2, draw2: 3, wild: 4, wild4: 5 } as const;
  const sorted = $derived(
    [...cards].sort(
      (a, b) =>
        (a.color ? COLOR_ORDER[a.color] : 9) - (b.color ? COLOR_ORDER[b.color] : 9) ||
        KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
        (a.value ?? 0) - (b.value ?? 0) ||
        a.id - b.id,
    ),
  );

  let width = $state(800);
  let cardWidth = $state(96);

  // Overlap cards so the whole hand fits; on very small screens fall back to scrolling.
  const layout = $derived.by(() => {
    const n = sorted.length;
    const avail = width - 44; // padding + room for the fan's rotation
    const natural = cardWidth + 8;
    let step = n <= 1 ? natural : Math.min(natural, (avail - cardWidth) / (n - 1));
    const minStep = cardWidth * 0.32;
    const scroll = step < minStep;
    if (scroll) step = minStep;
    return { step, scroll, n };
  });

  const rot = (i: number) => {
    const mid = (layout.n - 1) / 2;
    return layout.scroll ? 0 : (i - mid) * Math.min(3, 26 / Math.max(layout.n, 1));
  };
  const drop = (i: number) => {
    const mid = (layout.n - 1) / 2;
    return layout.scroll ? 0 : Math.abs(i - mid) ** 2 * Math.min(1.6, 14 / Math.max(layout.n, 1));
  };

  $effect(() => {
    const el = document.documentElement;
    const update = () => {
      const v = getComputedStyle(el).getPropertyValue('--card-lg').trim();
      cardWidth = parseFloat(v) || 96;
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  });
</script>

<div class="hand" class:scroll={layout.scroll} bind:clientWidth={width} data-hand>
  <div class="row" style:--step="{layout.step}px">
    {#each sorted as card, i (card.id)}
      {@const canPlay = myTurn && playable.includes(card.id)}
      <div
        class="slot"
        class:can={canPlay}
        class:sel={selected === card.id}
        style:--rot="{rot(i)}deg"
        style:--drop="{drop(i)}px"
        style:z-index={i}
        animate:flip={{ duration: 280 }}
        in:fly={{ y: 60, duration: 300, delay: Math.min(i, 10) * 35 }}
      >
        <Card
          {card}
          size="lg"
          playable={canPlay}
          dimmed={myTurn && !canPlay}
          hidden={hidden.includes(card.id)}
          selected={selected === card.id}
          onclick={canPlay ? () => onplay(card) : undefined}
        />
      </div>
    {/each}
  </div>
</div>

<style>
  .hand {
    width: 100%;
    display: flex;
    justify-content: center;
    padding: 26px 12px 14px;
    overflow: visible;
  }

  .hand.scroll {
    justify-content: flex-start;
    overflow-x: auto;
    overflow-y: visible;
    scrollbar-width: none;
    padding-top: 30px;
  }

  .row {
    display: flex;
    align-items: flex-end;
    margin: 0 auto;
  }

  .slot {
    flex: none;
    width: var(--step);
    transform: translateY(var(--drop)) rotate(var(--rot));
    transform-origin: 50% 120%;
    transition: transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .slot:last-child {
    width: auto;
  }

  .slot.can {
    transform: translateY(calc(var(--drop) - 14px)) rotate(var(--rot));
  }

  .slot.can:hover,
  .slot.can:focus-within,
  .slot.sel {
    transform: translateY(calc(var(--drop) - 30px)) rotate(var(--rot)) scale(1.04);
    z-index: 100 !important;
  }
</style>
