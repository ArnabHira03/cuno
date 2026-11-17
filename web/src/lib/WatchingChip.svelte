<script lang="ts">
  // "👁 N watching", shown to everyone in the room; tap for the names.
  let { names }: { names: string[] } = $props();
  let open = $state(false);
  let root = $state<HTMLElement>();

  function onDocClick(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
</script>

<svelte:document onclick={onDocClick} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

{#if names.length > 0}
  <span class="wrap" bind:this={root}>
    <button class="chip watching" onclick={() => (open = !open)} aria-expanded={open}>
      <span aria-hidden="true">👁</span> {names.length} watching
    </button>
    {#if open}
      <ul class="pop panel" role="list">
        {#each names as n, i (i)}<li>{n}</li>{/each}
      </ul>
    {/if}
  </span>
{/if}

<style>
  .wrap {
    position: relative;
    display: inline-flex;
  }

  .watching {
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font: inherit;
    font-size: 0.8rem;
    white-space: nowrap;
  }

  .watching:focus-visible {
    outline: 2px solid var(--accent);
  }

  .pop {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 60;
    margin: 0;
    padding: 8px 12px;
    list-style: none;
    min-width: 140px;
    max-height: 240px;
    overflow-y: auto;
    font-size: 0.85rem;
  }

  .pop li + li {
    margin-top: 4px;
  }
</style>
