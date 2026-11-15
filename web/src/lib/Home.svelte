<script lang="ts">
  import Card from './Card.svelte';
  import type { Card as CardT } from './types';

  let {
    initialCode = '',
    initialName = '',
    error = null,
    busy = false,
    onenter,
  }: {
    initialCode?: string;
    initialName?: string;
    error?: string | null;
    busy?: boolean;
    onenter: (code: string | null, name: string) => void;
  } = $props();

  // Initial values only; the parent re-mounts Home when they change.
  // svelte-ignore state_referenced_locally
  let name = $state(initialName);
  // svelte-ignore state_referenced_locally
  let code = $state(initialCode);
  const nameOk = $derived(name.trim().length > 0);
  const codeOk = $derived(/^[A-Za-z]{4}$/.test(code.trim()));

  const hero: CardT[] = [
    { id: -1, kind: 'number', color: 'red', value: 7 },
    { id: -2, kind: 'reverse', color: 'yellow', value: null },
    { id: -3, kind: 'wild4', color: null, value: null },
    { id: -4, kind: 'skip', color: 'green', value: null },
    { id: -5, kind: 'draw2', color: 'blue', value: null },
  ];
</script>

<div class="home">
  <div class="hero" aria-hidden="true">
    {#each hero as c, i (c.id)}
      <div class="hero-card" style:--i={i - 2}><Card card={c} size="md" /></div>
    {/each}
  </div>

  <h1 class="title">cuno</h1>
  <p class="tag">The colour-matching card game for you and your friends. 2–10 players, no sign-up.</p>

  <form class="panel form" onsubmit={(e) => e.preventDefault()}>
    <label>
      <span>Your nickname</span>
      <input class="field" bind:value={name} maxlength="16" placeholder="e.g. Arnav" autocomplete="nickname" />
    </label>

    {#if !initialCode}
      <button class="btn primary" type="button" disabled={!nameOk || busy} onclick={() => onenter(null, name.trim())}>
        Create a room
      </button>
      <div class="or"><span>or join one</span></div>
    {/if}

    <div class="join">
      <input
        class="field code"
        bind:value={code}
        maxlength="4"
        placeholder="CODE"
        autocapitalize="characters"
        aria-label="Room code"
      />
      <button
        class="btn {initialCode ? 'primary' : ''}"
        type="submit"
        disabled={!nameOk || !codeOk || busy}
        onclick={() => onenter(code.trim().toUpperCase(), name.trim())}
      >
        Join
      </button>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </form>
</div>

<style>
  .home {
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    gap: 10px;
  }

  .hero {
    position: relative;
    height: 150px;
    width: 300px;
    margin-bottom: 10px;
  }

  .hero-card {
    position: absolute;
    left: 50%;
    bottom: 0;
    margin-left: -43px;
    transform-origin: 50% 140%;
    transform: rotate(calc(var(--i) * 13deg));
    animation: deal 700ms cubic-bezier(0.2, 0.9, 0.3, 1.2) both;
    animation-delay: calc((var(--i) + 2) * 70ms);
  }

  @keyframes deal {
    from {
      transform: translateY(80px) rotate(0deg);
      opacity: 0;
    }
  }

  .title {
    margin: 0;
    font: 700 clamp(3rem, 12vw, 4.5rem) var(--font-display);
    letter-spacing: -0.03em;
    background: linear-gradient(90deg, var(--c-red), var(--c-yellow), var(--c-green), var(--c-blue));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    line-height: 1;
  }

  .tag {
    margin: 0 0 14px;
    color: var(--text-dim);
    text-align: center;
    max-width: 34ch;
  }

  .form {
    width: min(380px, 100%);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--text-dim);
  }

  .or {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--text-dim);
    font-size: 0.8rem;
  }

  .or::before,
  .or::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  .join {
    display: flex;
    gap: 8px;
  }

  .code {
    text-transform: uppercase;
    letter-spacing: 0.3em;
    font-family: var(--font-display);
    font-weight: 600;
    text-align: center;
  }

  .error {
    margin: 0;
    color: var(--danger);
    font-size: 0.9rem;
    text-align: center;
  }
</style>
