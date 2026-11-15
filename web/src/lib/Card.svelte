<script lang="ts">
  import type { Card } from './types';

  type Size = 'xs' | 'sm' | 'md' | 'lg';
  let {
    card = null,
    size = 'md',
    playable = false,
    dimmed = false,
    hidden = false,
    selected = false,
    onclick,
    label,
  }: {
    card?: Card | null;
    size?: Size;
    playable?: boolean;
    dimmed?: boolean;
    hidden?: boolean;
    selected?: boolean;
    onclick?: () => void;
    label?: string;
  } = $props();

  const widths: Record<Size, string> = { xs: '22px', sm: '40px', md: 'var(--card-md, 86px)', lg: 'var(--card-lg, 96px)' };

  const symbol = $derived.by(() => {
    if (!card) return '';
    switch (card.kind) {
      case 'number':
        return String(card.value);
      case 'draw2':
        return '+2';
      case 'wild4':
        return '+4';
      default:
        return '';
    }
  });

  const describe = (c: Card | null) => {
    if (!c) return 'face-down card';
    const color = c.color ?? '';
    const names: Record<string, string> = {
      number: String(c.value),
      skip: 'skip',
      reverse: 'reverse',
      draw2: 'draw two',
      wild: 'wild',
      wild4: 'wild draw four',
    };
    return `${color} ${names[c.kind]}`.trim();
  };
</script>

{#snippet glyph(c: Card, corner: boolean)}
  {#if c.kind === 'skip'}
    <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="3" />
      <line x1="6" y1="18" x2="18" y2="6" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
    </svg>
  {:else if c.kind === 'reverse'}
    <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
      <path d="M5 10a7 7 0 0 1 12-4.2" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" />
      <path d="M18.8 2.6 17.6 6.4 13.8 5.6" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M19 14a7 7 0 0 1-12 4.2" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" />
      <path d="M5.2 21.4 6.4 17.6 10.2 18.4" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  {:else if c.kind === 'wild' && corner}
    <span class="mini-wheel"></span>
  {:else if c.kind === 'wild'}
    <span></span>
  {:else}
    <span class:underline={c.kind === 'number' && (c.value === 6 || c.value === 9)}>{symbol}</span>
  {/if}
{/snippet}

<button
  type="button"
  class="card {size}"
  class:back={!card}
  class:playable
  class:dimmed
  class:hidden
  class:selected
  class:interactive={!!onclick}
  style:--w={widths[size]}
  style:--c={card ? (card.color ? `var(--c-${card.color})` : 'var(--c-wild)') : undefined}
  disabled={!onclick}
  aria-label={label ?? describe(card)}
  data-card-id={card?.id}
  {onclick}
>
  <span class="face">
  {#if card}
    <span class="frame">
      {#if size !== 'xs'}
        <span class="corner tl">{@render glyph(card, true)}</span>
        <span class="corner br">{@render glyph(card, true)}</span>
      {/if}
      <span class="emblem" class:wheel={card.kind === 'wild' || card.kind === 'wild4'}>
        <span class="emblem-inner">{@render glyph(card, false)}</span>
      </span>
    </span>
  {:else}
    <span class="frame back-frame">
      <span class="wordmark">cuno</span>
    </span>
  {/if}
  </span>
</button>

<style>
  .card {
    all: unset;
    box-sizing: border-box;
    position: relative;
    display: block;
    flex: none;
    width: var(--w);
    aspect-ratio: 2 / 3;
    container-type: inline-size;
    border-radius: calc(var(--w) * 0.12);
    font-family: var(--font-display);
    user-select: none;
    transition:
      transform 160ms cubic-bezier(0.2, 0.8, 0.2, 1),
      box-shadow 160ms ease,
      filter 160ms ease,
      opacity 160ms ease;
  }

  /* cqw units resolve against the .card container, so everything scales with card size. */
  .face {
    position: absolute;
    inset: 0;
    display: block;
    border-radius: 12cqw;
    padding: 5.5cqw;
    background: #fbfbf8;
    box-shadow:
      0 1px 0 rgba(255, 255, 255, 0.6) inset,
      0 2px 4px rgba(0, 0, 0, 0.25),
      0 6px 14px rgba(0, 0, 0, 0.18);
  }

  .card.interactive {
    cursor: pointer;
  }

  .card.hidden {
    opacity: 0;
  }

  .card.dimmed {
    filter: saturate(0.55) brightness(0.72);
  }

  .card.playable .face {
    box-shadow:
      0 0 0 3px var(--accent),
      0 0 18px color-mix(in srgb, var(--accent) 60%, transparent),
      0 8px 18px rgba(0, 0, 0, 0.3);
  }

  .card:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  .frame {
    position: relative;
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    border-radius: 8cqw;
    overflow: hidden;
    background:
      radial-gradient(120% 80% at 30% 15%, rgba(255, 255, 255, 0.22), transparent 55%),
      var(--c);
    color: #fff;
  }

  .emblem {
    width: 64cqw;
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    border-radius: 20cqw;
    background: #fff;
    transform: rotate(45deg);
    box-shadow: 0 2px 0 rgba(0, 0, 0, 0.12);
    color: var(--c);
  }

  .emblem.wheel {
    background: conic-gradient(var(--c-red) 0 25%, var(--c-yellow) 0 50%, var(--c-green) 0 75%, var(--c-blue) 0);
    border: 3.5cqw solid #fff;
    color: #fff;
  }

  .emblem-inner {
    transform: rotate(-45deg);
    display: grid;
    place-items: center;
    font-weight: 700;
    font-size: 40cqw;
    line-height: 1;
    letter-spacing: -0.04em;
  }

  .emblem.wheel .emblem-inner {
    font-size: 30cqw;
    text-shadow:
      0 0 3cqw rgba(0, 0, 0, 0.55),
      0 1.5cqw 0 rgba(0, 0, 0, 0.35);
    -webkit-text-stroke: 1.2cqw #1b1e2b;
    paint-order: stroke fill;
  }

  .emblem-inner :global(.icon) {
    width: 38cqw;
    height: 38cqw;
  }

  .corner {
    position: absolute;
    display: grid;
    place-items: center;
    font-weight: 700;
    font-size: 17cqw;
    line-height: 1;
    color: #fff;
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.25);
  }

  .corner :global(.icon) {
    width: 17cqw;
    height: 17cqw;
  }

  .corner.tl {
    top: 5cqw;
    left: 7cqw;
  }

  .corner.br {
    bottom: 5cqw;
    right: 7cqw;
    transform: rotate(180deg);
  }

  .mini-wheel {
    width: 15cqw;
    height: 15cqw;
    border-radius: 50%;
    background: conic-gradient(var(--c-red) 0 25%, var(--c-yellow) 0 50%, var(--c-green) 0 75%, var(--c-blue) 0);
    border: 1.5cqw solid #fff;
  }

  .underline {
    text-decoration: underline;
    text-decoration-thickness: 3cqw;
    text-underline-offset: 3cqw;
  }

  /* back */
  .back-frame {
    background:
      radial-gradient(90% 60% at 50% 40%, #2a3350, transparent 70%),
      repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.035) 0 4cqw, transparent 4cqw 8cqw),
      #151a2b;
  }

  .wordmark {
    transform: rotate(-24deg);
    font-weight: 700;
    font-size: 26cqw;
    letter-spacing: -0.02em;
    padding: 4cqw 9cqw 6cqw;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--c-red), var(--c-yellow), var(--c-green), var(--c-blue));
    color: #fff;
    text-shadow: 0 1.5cqw 0 rgba(0, 0, 0, 0.3);
    box-shadow: 0 0 0 2cqw rgba(255, 255, 255, 0.85);
  }

  .card.xs .frame,
  .card.sm .frame {
    border-radius: 9cqw;
  }

  .card.xs .face {
    padding: 7cqw;
  }

  .card.xs .wordmark {
    font-size: 0;
    padding: 0;
    width: 50cqw;
    height: 26cqw;
  }
</style>
