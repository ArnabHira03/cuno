<script lang="ts">
  import Avatar from './Avatar.svelte';
  import type { SeatEffect } from './fx.svelte';
  import type { PlayerInfo } from './types';

  let {
    player,
    count,
    score,
    active,
    host,
    dealer,
    unoCalled,
    canCatch,
    deadline,
    total,
    effect,
    x,
    y,
    compact = false,
    oncatch,
    onselect,
  }: {
    player: PlayerInfo;
    count: number;
    score: number;
    active: boolean;
    host: boolean;
    dealer: boolean;
    unoCalled: boolean;
    canCatch: boolean;
    deadline: number | null;
    total: number;
    effect?: SeatEffect;
    x: number;
    y: number;
    compact?: boolean;
    oncatch: () => void;
    /** Spectators: tap the seat to watch this player. */
    onselect?: () => void;
  } = $props();

  const fan = $derived(Math.min(count, 7));
</script>

<!-- role/tabindex are only set together, when the seat is selectable -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="seat"
  class:compact
  class:active
  class:away={!player.connected}
  class:shake={effect?.kind === 'shake'}
  style:--x="{x}%"
  style:--y="{y}%"
  data-seat-anchor={player.seat}
  class:selectable={!!onselect}
  role={onselect ? 'button' : undefined}
  tabindex={onselect ? 0 : undefined}
  title={onselect ? `Watch ${player.name}` : undefined}
  onclick={onselect}
  onkeydown={(e) => onselect && (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onselect())}
>
  <div class="avatar-wrap">
    <Avatar name={player.name} seat={player.seat} {active} {deadline} {total} away={!player.connected} />
    {#if host}
      <span class="crown" title="Host">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 18 5 7l5 5 2-7 2 7 5-5 2 11z" fill="currentColor" /></svg>
      </span>
    {/if}
    {#if dealer}<span class="dealer" title="Dealer">D</span>{/if}
    <div class="fan" aria-hidden="true">
      {#each { length: fan } as _, i}
        <span class="mini" style:--i={i - (fan - 1) / 2}></span>
      {/each}
    </div>
  </div>

  <div class="label">
    <span class="name">{player.name}</span>
    <span class="meta">
      <b>{count}</b>
      {count === 1 ? 'card' : 'cards'}<span class="pts">{' · '}{score} pts</span>
    </span>
    {#if !player.connected}<span class="tag away-tag">away</span>{/if}
  </div>

  {#if count === 1 && unoCalled}
    <span class="uno-badge">CUNO</span>
  {/if}
  {#if canCatch}
    <button
      class="catch"
      onclick={(e) => {
        e.stopPropagation();
        oncatch();
      }}>Catch!</button
    >
  {/if}

  {#if effect && effect.kind !== 'shake'}
    {#key effect.key}
      <span class="effect {effect.kind}">
        {#if effect.kind === 'skip'}
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" /><line x1="5.5" y1="18.5" x2="18.5" y2="5.5" stroke="currentColor" stroke-width="3" stroke-linecap="round" /></svg>
        {:else if effect.kind === 'timeout'}
          ⏱
        {:else}
          {effect.text}
        {/if}
      </span>
    {/key}
  {/if}
</div>

<style>
  .seat {
    position: absolute;
    left: var(--x);
    top: var(--y);
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    width: 112px;
    transition:
      left 500ms cubic-bezier(0.2, 0.8, 0.2, 1),
      top 500ms cubic-bezier(0.2, 0.8, 0.2, 1);
    z-index: 2;
  }

  .avatar-wrap {
    position: relative;
  }

  .seat.selectable {
    cursor: pointer;
    border-radius: 14px;
  }

  .seat.selectable:hover .label,
  .seat.selectable:focus-visible .label {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .seat.selectable:focus-visible {
    outline: none;
  }

  .crown {
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%) rotate(-8deg);
    width: 20px;
    color: #ffd34d;
    filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.5));
  }

  .dealer {
    position: absolute;
    bottom: -2px;
    left: -6px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font: 700 10px var(--font-display);
    background: #fff;
    color: #222;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  }

  .fan {
    position: absolute;
    right: -26px;
    bottom: -4px;
    width: 30px;
    height: 34px;
  }

  .mini {
    position: absolute;
    left: 8px;
    bottom: 0;
    width: 15px;
    height: 22px;
    border-radius: 3px;
    background: linear-gradient(135deg, #2a3350, #151a2b);
    border: 1.5px solid #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
    transform-origin: 50% 120%;
    transform: rotate(calc(var(--i) * 11deg));
    transition: transform 250ms ease;
  }

  .label {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4px 10px;
    border-radius: 12px;
    background: rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(6px);
    max-width: 100%;
    color: #fff;
  }

  .active .label {
    background: color-mix(in srgb, var(--accent) 88%, black);
    color: var(--accent-ink);
  }

  .name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 0.92rem;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .meta {
    font-size: 0.72rem;
    opacity: 0.85;
    white-space: nowrap;
  }

  .tag {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .away-tag {
    color: #ffb3b5;
  }

  .uno-badge {
    position: absolute;
    top: -6px;
    right: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font: 700 0.75rem var(--font-display);
    background: var(--c-red);
    color: #fff;
    box-shadow: 0 0 0 2px #fff, 0 4px 10px rgba(0, 0, 0, 0.4);
    transform: rotate(8deg);
  }

  .catch {
    border: 0;
    padding: 4px 12px;
    border-radius: 999px;
    font: 700 0.85rem var(--font-display);
    background: var(--danger);
    color: #fff;
    box-shadow: 0 0 0 2px #fff, 0 6px 16px rgba(0, 0, 0, 0.4);
    animation: pulse 0.8s ease-in-out infinite;
  }

  .effect {
    position: absolute;
    top: 6px;
    left: 50%;
    pointer-events: none;
    font: 700 1.6rem var(--font-display);
    color: #fff;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
    animation: pop 1.4s cubic-bezier(0.2, 0.9, 0.3, 1.3) forwards;
    z-index: 3;
  }

  .effect.plus {
    color: #fff;
    -webkit-text-stroke: 1px rgba(0, 0, 0, 0.4);
    font-size: 2rem;
  }

  .effect.uno {
    padding: 4px 12px;
    border-radius: 14px 14px 14px 2px;
    background: var(--c-red);
    font-size: 1.2rem;
    box-shadow: 0 0 0 2px #fff;
  }

  .effect.skip svg {
    width: 56px;
    height: 56px;
    color: var(--danger);
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.5));
  }

  .shake {
    animation: shake 0.5s ease;
  }

  @keyframes pop {
    0% {
      transform: translate(-50%, 10px) scale(0.4);
      opacity: 0;
    }
    18% {
      transform: translate(-50%, -18px) scale(1.15);
      opacity: 1;
    }
    75% {
      transform: translate(-50%, -26px) scale(1);
      opacity: 1;
    }
    100% {
      transform: translate(-50%, -40px) scale(0.9);
      opacity: 0;
    }
  }

  @keyframes shake {
    0%,
    100% {
      transform: translate(-50%, -50%);
    }
    20%,
    60% {
      transform: translate(calc(-50% - 7px), -50%);
    }
    40%,
    80% {
      transform: translate(calc(-50% + 7px), -50%);
    }
  }

  @keyframes pulse {
    50% {
      transform: scale(1.08);
    }
  }

  /* Compact table (phones, small windows, crowded rooms): a scrolling strip of chips. */
  .seat.compact {
    position: relative;
    left: auto;
    top: auto;
    transform: none;
    width: 76px;
    gap: 4px;
    flex: none;
  }
  .seat.compact.shake {
    animation-name: shake-flat;
  }
  .compact .label {
    padding: 2px 6px;
  }
  .compact .name {
    font-size: 0.78rem;
    max-width: 70px;
  }
  .compact .meta {
    font-size: 0.66rem;
  }
  .compact .fan,
  .compact .pts {
    display: none;
  }
  @keyframes shake-flat {
    20%,
    60% {
      transform: translateX(-6px);
    }
    40%,
    80% {
      transform: translateX(6px);
    }
  }
</style>
