<script lang="ts">
  // Player avatar with an optional countdown ring for the active turn.
  let {
    name,
    seat,
    size = 52,
    active = false,
    deadline = null,
    total = 30,
    away = false,
  }: {
    name: string;
    seat: number;
    size?: number;
    active?: boolean;
    deadline?: number | null;
    total?: number;
    away?: boolean;
  } = $props();

  const HUES = [265, 190, 330, 25, 150, 210, 45, 300, 0, 120];
  const hue = $derived(HUES[seat % HUES.length]);
  const initial = $derived((name.trim()[0] ?? '?').toUpperCase());

  const R = 46;
  const C = 2 * Math.PI * R;
  // Elapsed fraction of the turn at render time, so the ring resumes correctly.
  const ring = $derived.by(() => {
    if (!active || !deadline) return null;
    const left = Math.max(0, (deadline - Date.now()) / 1000);
    return { left, elapsed: Math.max(0, total - left) };
  });
</script>

<div class="avatar" class:active class:away style:--size="{size}px" style:--hue={hue}>
  <div class="face">{initial}</div>
  {#if ring}
    {#key deadline}
      <svg viewBox="0 0 100 100" class="ring" aria-hidden="true">
        <circle cx="50" cy="50" r={R} class="track" />
        <circle
          cx="50"
          cy="50"
          r={R}
          class="progress"
          style:stroke-dasharray={C}
          style:--c={C}
          style:animation-duration="{total}s"
          style:animation-delay="-{ring.elapsed}s"
        />
      </svg>
    {/key}
  {/if}
</div>

<style>
  .avatar {
    position: relative;
    width: var(--size);
    height: var(--size);
    flex: none;
  }

  .face {
    position: absolute;
    inset: 4px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: calc(var(--size) * 0.4);
    color: #fff;
    background: linear-gradient(145deg, hsl(var(--hue) 70% 62%), hsl(var(--hue) 60% 42%));
    box-shadow:
      0 0 0 2px rgba(255, 255, 255, 0.85),
      0 4px 12px rgba(0, 0, 0, 0.35);
    transition: box-shadow 200ms ease, transform 200ms ease;
  }

  .active .face {
    box-shadow:
      0 0 0 2px #fff,
      0 0 0 6px color-mix(in srgb, var(--accent) 50%, transparent),
      0 0 28px color-mix(in srgb, var(--accent) 70%, transparent);
    transform: scale(1.06);
  }

  .away .face {
    filter: grayscale(1) brightness(0.7);
  }

  .ring {
    position: absolute;
    inset: -5px;
    width: calc(100% + 10px);
    height: calc(100% + 10px);
    transform: rotate(-90deg);
    pointer-events: none;
  }

  .track {
    fill: none;
    stroke: rgba(255, 255, 255, 0.12);
    stroke-width: 5;
  }

  .progress {
    fill: none;
    stroke: var(--accent);
    stroke-width: 5;
    stroke-linecap: round;
    stroke-dashoffset: 0;
    animation-name: drain;
    animation-timing-function: linear;
    animation-fill-mode: both;
  }

  @keyframes drain {
    70% {
      stroke: var(--accent);
    }
    100% {
      stroke-dashoffset: var(--c);
      stroke: var(--danger);
    }
  }
</style>
