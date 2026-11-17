<script lang="ts">
  import { flip } from 'svelte/animate';
  import { fly } from 'svelte/transition';
  import Card from './Card.svelte';
  import { sortCards } from './cardSort';
  import { touchHand } from './touchHand';
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

  const sorted = $derived(sortCards(cards));

  let width = $state(800);
  let cardWidth = $state(96);

  // Touch devices: a swipe across the hand moves the lift (see touchHand.ts), so the
  // hand must never become a scrolling strip there.
  const coarse = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;

  // Overlap cards so the whole hand fits. With a mouse, very large hands fall back to
  // scrolling; on touch they keep overlapping, since the lifted card comes to the front.
  const layout = $derived.by(() => {
    const n = sorted.length;
    // Room the outermost cards stick out sideways once rotated (see rot(); rotation is
    // about 50% 120%, cards are 2:3), plus a little for the lifted card's scale.
    const tilt = (((n - 1) / 2) * Math.min(3, 26 / Math.max(n, 1)) * Math.PI) / 180;
    const overhang = Math.max(0, 1.8 * cardWidth * Math.sin(tilt) - (cardWidth / 2) * (1 - Math.cos(tilt)));
    const avail = width - 24 - Math.max(20, 2 * overhang + 6); // padding + fan overhang
    const natural = cardWidth + 8;
    let step = n <= 1 ? natural : Math.min(natural, (avail - cardWidth) / (n - 1));
    const minStep = coarse ? 6 : cardWidth * 0.32;
    const scroll = !coarse && step < minStep;
    if (step < minStep) step = minStep;
    return { step, scroll, n };
  });

  // Touch-lifted card (by id). Mouse users never set this; they use :hover.
  let lifted = $state<number | null>(null);
  $effect(() => {
    if (lifted !== null && !cards.some((c) => c.id === lifted)) lifted = null;
  });
  const liftedIndex = $derived(lifted === null ? null : sorted.findIndex((c) => c.id === lifted));

  function tapped(i: number) {
    const card = sorted[i];
    if (card && myTurn && playable.includes(card.id)) onplay(card);
  }

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
  <div
    class="row"
    style:--step="{layout.step}px"
    use:touchHand={{
      count: sorted.length,
      step: layout.step,
      lifted: liftedIndex,
      onlift: (i) => (lifted = sorted[i]?.id ?? null),
      ontap: tapped,
      onclear: () => (lifted = null),
    }}
  >
    {#each sorted as card, i (card.id)}
      {@const canPlay = myTurn && playable.includes(card.id)}
      <div
        class="slot"
        class:can={canPlay}
        class:sel={selected === card.id}
        class:lift={lifted === card.id}
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
    /* A swipe over the hand moves the lift instead of panning or scrolling the page. */
    touch-action: none;
    -webkit-touch-callout: none;
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

  /* Hover only where a real hover exists, so a tap never leaves a card stuck up. */
  @media (hover: hover) and (pointer: fine) {
    .slot.can:hover {
      transform: translateY(calc(var(--drop) - 30px)) rotate(var(--rot)) scale(1.04);
      z-index: 100 !important;
    }
  }

  .slot.can:has(:global(:focus-visible)),
  .slot.sel,
  .slot.lift {
    transform: translateY(calc(var(--drop) - 30px)) rotate(var(--rot)) scale(1.04);
    z-index: 100 !important;
  }

  @media (pointer: coarse) {
    .slot {
      will-change: transform;
    }
  }
</style>
