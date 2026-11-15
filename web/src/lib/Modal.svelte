<script lang="ts">
  import type { Snippet } from 'svelte';
  import { fade, scale } from 'svelte/transition';

  let { title, children, wide = false }: { title?: string; children: Snippet; wide?: boolean } = $props();
</script>

<div class="backdrop" transition:fade={{ duration: 160 }}>
  <div class="modal panel" class:wide role="dialog" aria-modal="true" aria-label={title} transition:scale={{ start: 0.92, duration: 220 }}>
    {#if title}<h2>{title}</h2>{/if}
    {@render children()}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    place-items: center;
    padding: 16px;
    background: rgba(5, 8, 14, 0.55);
    backdrop-filter: blur(3px);
  }

  .modal {
    width: min(420px, 100%);
    max-height: calc(100dvh - 32px);
    overflow: auto;
    padding: 22px;
    background: color-mix(in srgb, var(--bg) 88%, transparent);
  }

  .modal.wide {
    width: min(640px, 100%);
  }

  h2 {
    margin: 0 0 14px;
    font: 700 1.4rem var(--font-display);
    text-align: center;
  }
</style>
