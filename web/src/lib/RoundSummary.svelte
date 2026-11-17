<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Card from './Card.svelte';
  import { client } from './client.svelte';
  import Modal from './Modal.svelte';
  import type { GameView, RoomState } from './types';

  let { state: s }: { state: RoomState } = $props();
  const g = $derived(s.game as GameView);
  const lr = $derived(g.last_round!);
  const over = $derived(g.phase === 'game_over');
  const isHost = $derived(s.you !== null && s.host === s.you);
  const winnerName = $derived(lr.winner === s.you ? 'You' : s.players[lr.winner].name);
  const ranking = $derived(
    s.players.map((p) => ({ ...p, score: g.scores[p.seat] })).sort((a, b) => b.score - a.score),
  );
</script>

<Modal title={over ? '🏆 Game over' : 'Round over'} wide>
  <p class="headline">
    <b>{winnerName}</b>
    {over ? (lr.winner === s.you ? 'win the game!' : 'wins the game!') : lr.winner === s.you ? 'win the round' : 'wins the round'}
    <span class="pts">+{lr.points}</span>
  </p>

  <ol class="board">
    {#each ranking as p (p.seat)}
      {@const left = lr.hands[String(p.seat)] ?? []}
      <li class:winner={p.seat === lr.winner}>
        <Avatar name={p.name} seat={p.seat} size={36} />
        <div class="body">
          <div class="line">
            <span class="name">{p.seat === s.you ? `${p.name} (you)` : p.name}</span>
            <span class="score">{p.score}</span>
          </div>
          <div class="bar"><span style:width="{Math.min(100, (p.score / g.target_score) * 100)}%"></span></div>
          {#if left.length}
            <div class="left">
              {#each left as c (c.id)}<Card card={c} size="xs" />{/each}
              <span class="minus">{lr.breakdown[String(p.seat)]} pts</span>
            </div>
          {/if}
        </div>
      </li>
    {/each}
  </ol>

  <div class="foot">
    {#if isHost}
      {#if over}
        <button class="btn primary" onclick={() => client.send({ type: 'new_game' })}>Back to lobby</button>
      {:else}
        <button class="btn primary" onclick={() => client.send({ type: 'next_round' })}>Deal next round</button>
      {/if}
    {:else}
      <p class="wait">Waiting for {s.host !== null ? s.players[s.host].name : 'the host'}…</p>
    {/if}
  </div>
</Modal>

<style>
  .headline {
    text-align: center;
    font-size: 1.1rem;
    margin: 0 0 18px;
  }

  .headline b {
    font-family: var(--font-display);
    font-size: 1.3rem;
  }

  .pts {
    display: inline-block;
    margin-left: 6px;
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-ink);
    font: 700 0.95rem var(--font-display);
  }

  .board {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  li {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 10px 12px;
    border-radius: 14px;
    background: var(--surface);
  }

  li.winner {
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .body {
    flex: 1;
    min-width: 0;
  }

  .line {
    display: flex;
    justify-content: space-between;
    font-family: var(--font-display);
    font-weight: 600;
  }

  .bar {
    height: 6px;
    border-radius: 999px;
    background: rgba(127, 127, 127, 0.25);
    margin: 6px 0;
    overflow: hidden;
  }

  .bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--c-green), var(--accent));
    transition: width 600ms ease;
  }

  .left {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    align-items: center;
  }

  .minus {
    margin-left: 6px;
    font-size: 0.75rem;
    color: var(--text-dim);
  }

  .foot {
    display: flex;
    justify-content: center;
    margin-top: 18px;
  }

  .wait {
    color: var(--text-dim);
    margin: 0;
  }
</style>
