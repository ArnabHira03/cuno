<script lang="ts">
  import { client, storageGet, storageSet } from './lib/client.svelte';
  import { fx } from './lib/fx.svelte';
  import Home from './lib/Home.svelte';
  import Lobby from './lib/Lobby.svelte';
  import Table from './lib/Table.svelte';

  client.hooks = fx;

  const codeFromPath = () => location.pathname.match(/^\/r\/([A-Za-z]{4})\/?$/)?.[1]?.toUpperCase() ?? '';

  const startCode = codeFromPath();
  let urlCode = $state(startCode);
  let creating = $state(false);
  let homeError = $state<string | null>(null);
  const savedName = storageGet('cuno:name') ?? '';

  // Coming back to a room we were already in (refresh, reopened tab): rejoin straight away.
  if (startCode && savedName && storageGet(`cuno:token:${startCode}`)) client.connect(startCode, savedName);

  async function enter(code: string | null, name: string) {
    homeError = null;
    storageSet('cuno:name', name);
    if (!code) {
      creating = true;
      try {
        const res = await fetch('/api/rooms', { method: 'POST' });
        code = (await res.json()).code as string;
      } catch {
        homeError = "Couldn't reach the server.";
        return;
      } finally {
        creating = false;
      }
    }
    history.pushState(null, '', `/r/${code}`);
    urlCode = code;
    client.connect(code, name);
  }

  // Leaving drops us back on the home screen (only on the transition, not on first load).
  let wasActive = false;
  $effect(() => {
    const active = client.status !== 'idle';
    if (wasActive && !active && location.pathname !== '/') {
      history.replaceState(null, '', '/');
      urlCode = '';
    }
    wasActive = active;
  });

  $effect(() => {
    if (client.error && !client.state) homeError = client.error.message;
  });

  const busy = $derived(creating || client.status === 'connecting');
</script>

<svelte:window onpopstate={() => (urlCode = codeFromPath())} />

{#if client.state && client.state.phase === 'lobby'}
  <Lobby state={client.state} />
{:else if client.state && client.state.game}
  <Table state={client.state} />
{:else}
  {#key urlCode}
    <Home initialCode={urlCode} initialName={savedName} error={homeError} {busy} onenter={enter} />
  {/key}
{/if}

{#if client.error?.code === 'replaced'}
  <div class="replaced panel">This game is open in another tab. <button class="btn" onclick={() => location.reload()}>Use it here</button></div>
{/if}

<div class="fx-layer" bind:this={fx.layer}></div>

<style>
  .fx-layer {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 45;
  }

  .fx-layer :global(.flight) {
    position: fixed;
    will-change: transform;
    filter: drop-shadow(0 12px 18px rgba(0, 0, 0, 0.35));
  }

  .replaced {
    position: fixed;
    inset: auto 16px 16px;
    z-index: 70;
    padding: 14px 18px;
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
  }

  :global(:root) {
    --card-lg: 96px;
    --card-md: 86px;
  }

  @media (max-width: 900px) {
    :global(:root) {
      --card-lg: 84px;
      --card-md: 76px;
    }
  }

  @media (max-width: 640px) {
    :global(:root) {
      --card-lg: 68px;
      --card-md: 64px;
    }
  }

  @media (max-height: 640px) and (min-width: 641px) {
    :global(:root) {
      --card-lg: 76px;
      --card-md: 66px;
    }
  }
</style>
