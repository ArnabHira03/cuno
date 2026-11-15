<script lang="ts">
  import { flip } from 'svelte/animate';
  import { scale } from 'svelte/transition';
  import Avatar from './Avatar.svelte';
  import { client } from './client.svelte';
  import type { RoomState } from './types';

  let { state: s }: { state: RoomState } = $props();
  const isHost = $derived(s.host === s.you);
  const link = $derived(`${location.origin}/r/${s.code}`);
  let copied = $state(false);

  async function copy() {
    try {
      if (navigator.share && matchMedia('(pointer: coarse)').matches) {
        await navigator.share({ title: 'Join my Cuno room', url: link });
        return;
      }
      await navigator.clipboard.writeText(link);
      copied = true;
      setTimeout(() => (copied = false), 1600);
    } catch {
      /* user cancelled share */
    }
  }
</script>

<div class="lobby">
  <div class="card panel">
    <p class="eyebrow">Room code</p>
    <h1 class="code">
      {#each s.code.split('') as ch, i}<span style:--i={i}>{ch}</span>{/each}
    </h1>
    <button class="btn" onclick={copy}>{copied ? 'Link copied ✓' : 'Share invite link'}</button>

    <div class="players">
      <p class="eyebrow">Players · {s.players.length}/10</p>
      <ul>
        {#each s.players as p (p.seat)}
          <li animate:flip={{ duration: 250 }} in:scale={{ start: 0.7, duration: 250 }}>
            <Avatar name={p.name} seat={p.seat} size={40} away={!p.connected} />
            <span class="name">{p.name}{p.seat === s.you ? ' (you)' : ''}</span>
            {#if s.host === p.seat}<span class="host">host</span>{/if}
          </li>
        {/each}
      </ul>
    </div>

    {#if isHost}
      <button class="btn primary start" disabled={s.players.length < 2} onclick={() => client.send({ type: 'start' })}>
        {s.players.length < 2 ? 'Waiting for friends…' : `Start game (${s.players.length} players)`}
      </button>
    {:else}
      <p class="wait">Waiting for {s.host !== null ? s.players[s.host].name : 'the host'} to start…</p>
    {/if}
    <button class="link" onclick={() => client.leave()}>Leave room</button>
  </div>
</div>

<style>
  .lobby {
    min-height: 100dvh;
    display: grid;
    place-items: center;
    padding: 24px 16px;
  }

  .card {
    width: min(440px, 100%);
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .eyebrow {
    margin: 0;
    font-size: 0.75rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .code {
    margin: 0;
    display: flex;
    gap: 8px;
    font: 700 3rem var(--font-display);
  }

  .code span {
    display: grid;
    place-items: center;
    width: 1.3em;
    height: 1.5em;
    border-radius: 12px;
    color: #fff;
    background: var(--c, var(--c-red));
    box-shadow: inset 0 -5px 0 rgba(0, 0, 0, 0.18);
    transform: rotate(calc((var(--i) - 1.5) * 4deg));
  }

  .code span:nth-child(1) {
    --c: var(--c-red);
  }
  .code span:nth-child(2) {
    --c: var(--c-yellow);
  }
  .code span:nth-child(3) {
    --c: var(--c-green);
  }
  .code span:nth-child(4) {
    --c: var(--c-blue);
  }

  .players {
    width: 100%;
    margin-top: 8px;
  }

  ul {
    list-style: none;
    padding: 0;
    margin: 10px 0 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  li {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 10px;
    border-radius: 12px;
    background: var(--surface);
  }

  .name {
    flex: 1;
    font-weight: 500;
  }

  .host {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-ink);
  }

  .start {
    width: 100%;
    margin-top: 6px;
  }

  .wait {
    color: var(--text-dim);
    margin: 6px 0 0;
  }

  .link {
    background: none;
    border: 0;
    color: var(--text-dim);
    text-decoration: underline;
    font-size: 0.85rem;
  }
</style>
