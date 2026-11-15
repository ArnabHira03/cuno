<script lang="ts">
  import { fly as flyT } from 'svelte/transition';
  import Avatar from './Avatar.svelte';
  import Card from './Card.svelte';
  import { client } from './client.svelte';
  import { fx } from './fx.svelte';
  import Hand from './Hand.svelte';
  import Modal from './Modal.svelte';
  import Piles from './Piles.svelte';
  import RoundSummary from './RoundSummary.svelte';
  import Seat from './Seat.svelte';
  import type { Card as CardT, Color, GameView, RoomState } from './types';

  let { state: s }: { state: RoomState } = $props();
  const g = $derived(s.game as GameView);
  const me = $derived(s.you);
  const n = $derived(s.players.length);
  const playing = $derived(g.phase === 'playing');
  const name = (seat: number) => (seat === me ? 'You' : (s.players[seat]?.name ?? '?'));

  const myTurn = $derived(playing && g.actor === me);
  const canDraw = $derived(playing && g.turn === me && !g.pending && g.drawn_card_id === null);
  const canKeep = $derived(playing && g.turn === me && !g.pending && g.drawn_card_id !== null);
  const challengeMe = $derived(playing && g.pending?.type === 'challenge' && g.pending.victim === me);
  const chooseMe = $derived(playing && g.pending?.type === 'choose_color' && g.pending.seat === me);
  const unoAvailable = $derived(
    playing && g.hand.length > 0 && g.hand.length <= 2 && !g.uno_called[me],
  );
  const unoUrgent = $derived(
    unoAvailable && (g.uno_vulnerable === me || (g.hand.length === 2 && g.turn === me && g.playable.length > 0)),
  );

  let wildCard = $state<CardT | null>(null);
  let feltW = $state(1000);
  let feltH = $state(600);
  // Fall back to a strip of opponents when the ellipse would get crowded.
  const compact = $derived(feltW < 600 || feltH < 280 || (n > 5 && (feltH < 440 || feltW < 820)));
  let confirmLeave = $state(false);

  // Opponents sit around an ellipse in play order, starting on your left.
  const seats = $derived.by(() => {
    const others = n - 1;
    const span = Math.min(240, 60 * Math.max(others - 1, 0));
    const start = 270 - span / 2;
    return Array.from({ length: others }, (_, i) => {
      const seat = (me + i + 1) % n;
      const deg = others === 1 ? 270 : start + (span * i) / (others - 1);
      const rad = (deg * Math.PI) / 180;
      return { seat, x: 50 + 44 * Math.cos(rad), y: 52 + 42 * Math.sin(rad) };
    });
  });

  const status = $derived.by(() => {
    if (!playing) return '';
    const p = g.pending;
    if (p?.type === 'challenge') {
      return p.victim === me
        ? `${name(p.player)} played Wild +4 on you`
        : `${name(p.victim)} is deciding whether to challenge ${name(p.player)}`;
    }
    if (p?.type === 'choose_color') return p.seat === me ? 'Pick the starting colour' : `${name(p.seat)} is choosing a colour`;
    if (g.turn === me) {
      if (g.drawn_card_id !== null) return 'You can play the card you drew, or keep it';
      return g.playable.length ? 'Your turn — play a card' : 'Your turn — no match, draw a card';
    }
    return `${name(g.turn)}'s turn`;
  });

  function play(card: CardT) {
    if (card.kind === 'wild' || card.kind === 'wild4') {
      wildCard = card;
      return;
    }
    client.send({ type: 'play', card_id: card.id });
  }

  function pickColor(color: Color) {
    if (chooseMe) client.send({ type: 'choose_color', color });
    else if (wildCard) client.send({ type: 'play', card_id: wildCard.id, color });
    wildCard = null;
  }

  // Close the wild picker if the turn moved on underneath it.
  $effect(() => {
    if (wildCard && !(myTurn && g.playable.includes(wildCard.id))) wildCard = null;
  });

  function onKey(e: KeyboardEvent) {
    if (e.target instanceof HTMLInputElement) return;
    if (e.key === 'd' && canDraw) client.send({ type: 'draw' });
    if (e.key === 'k' && canKeep) client.send({ type: 'keep' });
    if (e.key === 'u' && unoAvailable) client.send({ type: 'call_uno' });
  }

  const COLORS: Color[] = ['red', 'yellow', 'green', 'blue'];
</script>

<svelte:window onkeydown={onKey} />

<div class="screen">
  <header class="topbar">
    <div class="brand">cuno</div>
    <div class="chips">
      <span class="chip">Room <b>{s.code}</b></span>
      <span class="chip">Round {g.round}</span>
      <span class="chip hide-sm">First to {g.target_score}</span>
    </div>
    <button class="btn ghost" onclick={() => (confirmLeave = true)}>Leave</button>
  </header>

  {#if client.status === 'reconnecting'}
    <div class="banner">Reconnecting…</div>
  {/if}

  <main class="felt-wrap" class:compact bind:clientWidth={feltW} bind:clientHeight={feltH}>
    <div class="felt">
      <div class="opponents">
        {#each seats as o (o.seat)}
          {@const p = s.players[o.seat]}
          <Seat
            player={p}
            count={g.hand_counts[o.seat]}
            score={g.scores[o.seat]}
            active={playing && g.actor === o.seat}
            host={s.host === o.seat}
            dealer={g.dealer === o.seat}
            unoCalled={g.uno_called[o.seat]}
            canCatch={playing && g.uno_vulnerable === o.seat}
            deadline={client.deadline}
            total={p.connected ? s.turn_seconds : 8}
            effect={fx.effects[o.seat]}
            x={o.x}
            y={o.y}
            {compact}
            oncatch={() => client.send({ type: 'catch', target: o.seat })}
          />
        {/each}
      </div>

      <div class="center">
        <Piles
          top={g.top}
          hiddenTop={fx.hiddenTop}
          drawCount={g.draw_count}
          color={g.current_color}
          direction={g.direction}
          {canDraw}
          ondraw={() => client.send({ type: 'draw' })}
        />
        <p class="status" class:mine={myTurn}>{status}</p>
      </div>
    </div>
  </main>

  <section class="me" class:active={myTurn}>
    <div class="me-bar">
      <div class="who" data-seat-anchor={me}>
        <Avatar
          name={s.players[me].name}
          seat={me}
          size={44}
          active={myTurn}
          deadline={client.deadline}
          total={s.turn_seconds}
        />
        <div class="who-text">
          <b>{s.players[me].name}</b>
          <span>{g.scores[me]} pts{#if s.host === me}{' · host'}{/if}</span>
        </div>
        {#if fx.effects[me] && fx.effects[me].kind !== 'shake'}
          {#key fx.effects[me].key}
            <span class="my-effect">{fx.effects[me].text ?? (fx.effects[me].kind === 'skip' ? 'Skipped' : '⏱')}</span>
          {/key}
        {/if}
      </div>
      <div class="actions">
        {#if canKeep}
          <button class="btn" onclick={() => client.send({ type: 'keep' })}>Keep <kbd>K</kbd></button>
        {/if}
        {#if canDraw}
          <button class="btn" onclick={() => client.send({ type: 'draw' })}>Draw <kbd>D</kbd></button>
        {/if}
        {#if unoAvailable}
          <button class="btn uno" class:urgent={unoUrgent} onclick={() => client.send({ type: 'call_uno' })}>UNO!</button>
        {:else if playing && g.uno_called[me] && g.hand.length <= 2}
          <span class="called">UNO called ✓</span>
        {/if}
      </div>
    </div>
    <div class:shake={fx.effects[me]?.kind === 'shake'}>
      <Hand
        cards={g.hand}
        playable={g.playable}
        hidden={fx.hiddenHand}
        myTurn={playing && g.turn === me && !g.pending}
        selected={wildCard?.id ?? null}
        onplay={play}
      />
    </div>
  </section>

  {#if wildCard || chooseMe}
    <Modal title={chooseMe ? 'Choose the starting colour' : 'Choose a colour'}>
      <div class="colors">
        {#each COLORS as c}
          <button class="color {c}" onclick={() => pickColor(c)}>{c}</button>
        {/each}
      </div>
      {#if wildCard}
        <button class="btn cancel" onclick={() => (wildCard = null)}>Cancel</button>
      {/if}
    </Modal>
  {/if}

  {#if challengeMe && g.pending?.type === 'challenge'}
    {@const offender = g.pending.player}
    <Modal title="Wild +4!">
      <p class="explain">
        <b>{name(offender)}</b> played a Wild Draw Four on you. It's only legal if they had no card matching the
        previous colour.
      </p>
      <ul class="explain">
        <li><b>Challenge:</b> if they bluffed, <i>they</i> draw 4 and you keep your turn. If not, you draw 6.</li>
        <li><b>Accept:</b> draw 4 and lose your turn.</li>
      </ul>
      <div class="row-btns">
        <button class="btn" onclick={() => client.send({ type: 'accept' })}>Accept (+4)</button>
        <button class="btn primary" onclick={() => client.send({ type: 'challenge' })}>Challenge</button>
      </div>
    </Modal>
  {/if}

  {#if fx.reveal}
    <Modal title="{fx.reveal.name}'s hand">
      <div class="reveal">
        {#each fx.reveal.cards as c (c.id)}<Card card={c} size="sm" />{/each}
      </div>
      <button class="btn primary cancel" onclick={() => (fx.reveal = null)}>Got it</button>
    </Modal>
  {/if}

  {#if g.phase !== 'playing' && g.last_round}
    <RoundSummary state={s} />
  {/if}

  {#if confirmLeave}
    <Modal title="Leave the game?">
      <p class="explain">Your seat stays in the game and plays automatically until the round ends.</p>
      <div class="row-btns">
        <button class="btn" onclick={() => (confirmLeave = false)}>Stay</button>
        <button class="btn danger" onclick={() => client.leave()}>Leave</button>
      </div>
    </Modal>
  {/if}

  <div class="toasts" aria-live="polite">
    {#each fx.toasts as t (t.id)}
      <div class="toast {t.tone}" in:flyT={{ y: -12, duration: 200 }} out:flyT={{ y: -12, duration: 200 }}>{t.text}</div>
    {/each}
  </div>
</div>

<style>
  .screen {
    height: 100dvh;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    grid-template-columns: minmax(0, 1fr);
    overflow: hidden;
  }

  .topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
  }

  .brand {
    font: 700 1.5rem var(--font-display);
    background: linear-gradient(90deg, var(--c-red), var(--c-yellow), var(--c-green), var(--c-blue));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .chips {
    display: flex;
    gap: 8px;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }

  .chip {
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    font-size: 0.8rem;
    white-space: nowrap;
  }

  .chip b {
    font-family: var(--font-display);
    letter-spacing: 0.08em;
  }

  .btn.ghost {
    padding: 0.4rem 0.9rem;
    font-size: 0.9rem;
    background: transparent;
  }

  .banner {
    position: fixed;
    top: 60px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 40;
    padding: 6px 14px;
    border-radius: 999px;
    background: var(--danger);
    color: #fff;
    font-weight: 600;
    font-size: 0.85rem;
  }

  .felt-wrap {
    min-height: 0;
    padding: 4px 16px 0;
    display: flex;
  }

  .felt {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 300px;
    border-radius: 50% / 46%;
    background:
      radial-gradient(ellipse at 50% 40%, var(--felt-1), var(--felt-2) 70%),
      var(--felt-2);
    box-shadow:
      inset 0 0 0 10px var(--felt-edge),
      inset 0 0 0 12px rgba(255, 255, 255, 0.08),
      inset 0 20px 60px rgba(0, 0, 0, 0.35),
      var(--shadow);
    margin: 30px 50px 40px;
  }

  .opponents {
    position: absolute;
    inset: 0;
  }

  .center {
    position: absolute;
    left: 50%;
    top: 52%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .status {
    margin: 64px 0 0;
    padding: 5px 14px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.3);
    color: #fff;
    font-size: 0.88rem;
    text-align: center;
    white-space: nowrap;
  }

  .status.mine {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: 600;
    animation: breathe 2s ease-in-out infinite;
  }

  @keyframes breathe {
    50% {
      box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent) 25%, transparent);
    }
  }

  .me {
    position: relative;
    min-width: 0;
    padding: 0 0 max(8px, env(safe-area-inset-bottom));
    background: linear-gradient(to top, rgba(0, 0, 0, 0.35), transparent);
    transition: background 300ms;
  }

  .me.active {
    background: linear-gradient(to top, color-mix(in srgb, var(--accent) 22%, transparent), transparent);
  }

  .me-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 16px;
    max-width: 1100px;
    margin: 0 auto;
  }

  .who {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .who-text {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }

  .who-text b {
    font-family: var(--font-display);
  }

  .who-text span {
    font-size: 0.78rem;
    color: var(--text-dim);
  }

  .my-effect {
    position: absolute;
    left: 50px;
    top: -18px;
    font: 700 1.6rem var(--font-display);
    color: var(--danger);
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
    animation: rise 1.4s ease forwards;
    pointer-events: none;
  }

  @keyframes rise {
    0% {
      opacity: 0;
      transform: translateY(10px) scale(0.6);
    }
    20% {
      opacity: 1;
      transform: translateY(-6px) scale(1.1);
    }
    100% {
      opacity: 0;
      transform: translateY(-30px);
    }
  }

  .actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  kbd {
    font: 600 0.7rem var(--font-body);
    opacity: 0.55;
    margin-left: 4px;
  }

  .btn.uno {
    background: var(--c-red);
    color: #fff;
    border-color: transparent;
    font-weight: 700;
    letter-spacing: 0.04em;
  }

  .btn.uno.urgent {
    animation: urgent 0.9s ease-in-out infinite;
  }

  @keyframes urgent {
    50% {
      transform: scale(1.08);
      box-shadow: 0 0 0 8px color-mix(in srgb, var(--c-red) 30%, transparent);
    }
  }

  .called {
    font-size: 0.85rem;
    color: var(--text-dim);
  }

  .shake {
    animation: shake-x 0.5s ease;
  }

  @keyframes shake-x {
    20%,
    60% {
      transform: translateX(-8px);
    }
    40%,
    80% {
      transform: translateX(8px);
    }
  }

  .colors {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .color {
    border: 0;
    aspect-ratio: 1.6;
    border-radius: 16px;
    color: #fff;
    font: 700 1.1rem var(--font-display);
    text-transform: capitalize;
    box-shadow: inset 0 -6px 0 rgba(0, 0, 0, 0.18);
    transition: transform 120ms;
  }

  .color:hover {
    transform: scale(1.04);
  }

  .color.red {
    background: var(--c-red);
  }
  .color.yellow {
    background: var(--c-yellow);
  }
  .color.green {
    background: var(--c-green);
  }
  .color.blue {
    background: var(--c-blue);
  }

  .cancel {
    display: block;
    margin: 16px auto 0;
  }

  .explain {
    color: var(--text-dim);
    line-height: 1.5;
    font-size: 0.95rem;
  }

  ul.explain {
    padding-left: 1.1rem;
  }

  .row-btns {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-top: 12px;
  }

  .reveal {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
  }

  .toasts {
    position: fixed;
    bottom: calc(var(--card-lg) * 1.5 + 96px);
    left: 50%;
    transform: translateX(-50%);
    z-index: 60;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    pointer-events: none;
    width: min(92vw, 460px);
  }

  .toast {
    padding: 8px 16px;
    border-radius: 999px;
    background: rgba(15, 20, 30, 0.88);
    color: #fff;
    font-size: 0.88rem;
    text-align: center;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .toast.good {
    border-color: color-mix(in srgb, var(--c-green) 70%, transparent);
  }

  .toast.bad {
    border-color: color-mix(in srgb, var(--danger) 70%, transparent);
  }

  @media (max-width: 900px) {
    .felt {
      margin: 30px 40px 36px;
    }
  }

  /* Compact: opponent strip on top, piles in the middle, no ellipse. */
  .compact .felt {
    margin: 0;
    border-radius: 28px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }
  .felt-wrap.compact {
    padding: 0 8px;
  }
  .compact .opponents {
    position: static;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 14px 10px 8px;
    scrollbar-width: none;
    justify-content: safe center;
    min-width: 0;
  }
  .compact .center {
    --ring: 230px;
    position: static;
    transform: none;
    flex: 1;
    justify-content: center;
    padding-bottom: 12px;
  }
  .compact .status {
    margin-top: 46px;
    white-space: normal;
    font-size: 0.8rem;
  }

  @media (max-width: 640px) {
    .hide-sm {
      display: none;
    }
    .topbar {
      padding: 8px 12px;
    }
    .me-bar {
      padding: 0 12px;
    }
    .who-text span {
      display: none;
    }
    .btn {
      padding: 0.6rem 1rem;
      font-size: 0.95rem;
    }
    kbd {
      display: none;
    }
  }
</style>
