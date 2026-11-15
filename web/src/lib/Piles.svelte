<script lang="ts">
  import Card from './Card.svelte';
  import type { Card as CardT, Color } from './types';

  let {
    top,
    hiddenTop,
    drawCount,
    color,
    direction,
    canDraw,
    ondraw,
  }: {
    top: CardT | null;
    hiddenTop: number | null;
    drawCount: number;
    color: Color | null;
    direction: 1 | -1;
    canDraw: boolean;
    ondraw: () => void;
  } = $props();

  // Keep the last few discards so the pile looks like a real messy stack.
  let history = $state<CardT[]>([]);
  $effect(() => {
    if (!top) return;
    const t = top;
    if (history.at(-1)?.id === t.id) return;
    history = [...history.filter((c) => c.id !== t.id).slice(-3), t];
  });
  const visible = $derived(history.filter((c) => c.id !== hiddenTop).slice(-4));
  const tilt = (id: number) => ((id * 37) % 25) - 12;
  const shift = (id: number) => ((id * 53) % 11) - 5;
</script>

<div class="piles" style:--glow={color ? `var(--c-${color})` : 'transparent'}>
  <svg class="direction" class:ccw={direction === -1} viewBox="0 0 200 200" aria-hidden="true">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0 0 10 5 0 10z" fill="currentColor" />
      </marker>
    </defs>
    {#each [0, 120, 240] as start}
      <path
        d={`M ${100 + 92 * Math.cos(((start + 15) * Math.PI) / 180)} ${100 + 92 * Math.sin(((start + 15) * Math.PI) / 180)} A 92 92 0 0 1 ${100 + 92 * Math.cos(((start + 95) * Math.PI) / 180)} ${100 + 92 * Math.sin(((start + 95) * Math.PI) / 180)}`}
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        marker-end={direction === 1 ? 'url(#arrow)' : undefined}
        marker-start={direction === -1 ? 'url(#arrow)' : undefined}
      />
    {/each}
  </svg>

  <div class="stack draw" data-pile="draw">
    <span class="under u2"></span>
    <span class="under u1"></span>
    <div class="draw-card" class:can={canDraw}>
      <Card size="md" onclick={canDraw ? ondraw : undefined} label="Draw a card" />
    </div>
    <span class="count">{drawCount}</span>
  </div>

  <div class="stack discard" data-pile="discard">
    <span class="halo"></span>
    {#each visible as c (c.id)}
      <div class="discarded" style:--r="{tilt(c.id)}deg" style:--s="{shift(c.id)}px">
        <Card card={c} size="md" />
      </div>
    {/each}
    {#if color}
      <span class="color-chip">{color}</span>
    {/if}
  </div>
</div>

<style>
  .piles {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(22px, 5vw, 48px);
    padding: 28px 36px;
  }

  .direction {
    position: absolute;
    left: 50%;
    top: 50%;
    width: var(--ring, 300px);
    height: var(--ring, 300px);
    margin: calc(var(--ring, 300px) / -2) 0 0 calc(var(--ring, 300px) / -2);
    color: color-mix(in srgb, var(--glow) 55%, rgba(255, 255, 255, 0.35));
    opacity: 0.6;
    animation: spin 18s linear infinite;
    pointer-events: none;
    transition: color 400ms ease;
  }

  .direction.ccw {
    animation-direction: reverse;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .stack {
    position: relative;
    width: var(--card-md, 86px);
    aspect-ratio: 2 / 3;
  }

  .under {
    position: absolute;
    inset: 0;
    border-radius: 12%;
    background: #151a2b;
    border: 2px solid #fbfbf8;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  }

  .u1 {
    transform: translate(3px, 3px);
  }

  .u2 {
    transform: translate(6px, 6px);
  }

  .draw-card {
    position: relative;
    border-radius: 12%;
    transition: transform 160ms ease;
  }

  .draw-card.can {
    animation: nudge 1.6s ease-in-out infinite;
  }

  .draw-card.can :global(.card .face) {
    box-shadow:
      0 0 0 3px var(--accent),
      0 0 22px color-mix(in srgb, var(--accent) 60%, transparent);
  }

  @keyframes nudge {
    50% {
      transform: translateY(-5px);
    }
  }

  .count {
    position: absolute;
    bottom: -26px;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.7);
  }

  .halo {
    position: absolute;
    inset: -18px;
    border-radius: 24px;
    background: radial-gradient(closest-side, color-mix(in srgb, var(--glow) 70%, transparent), transparent);
    filter: blur(6px);
    transition: background 400ms ease;
  }

  .discarded {
    position: absolute;
    inset: 0;
    transform: translate(var(--s), calc(var(--s) * -0.6)) rotate(var(--r));
  }

  .color-chip {
    position: absolute;
    bottom: -28px;
    left: 50%;
    transform: translateX(-50%);
    padding: 2px 10px;
    border-radius: 999px;
    font: 600 0.72rem var(--font-display);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #fff;
    background: var(--glow);
    box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
    transition: background 300ms;
  }

</style>
