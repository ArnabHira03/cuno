# Cuno Rules

Cuno follows the standard rules of the classic shedding card game Uno.
This file is the reference for the game engine: if the code and this file disagree, one of them is a bug.

Room size: **2–10 players**, one deck.

---

## 1. The deck (108 cards)

| Card | Per colour | Colours | Total |
|------|-----------|---------|-------|
| 0 | 1 | Red, Yellow, Green, Blue | 4 |
| 1–9 | 2 each | Red, Yellow, Green, Blue | 72 |
| Skip | 2 | Red, Yellow, Green, Blue | 8 |
| Reverse | 2 | Red, Yellow, Green, Blue | 8 |
| Draw Two | 2 | Red, Yellow, Green, Blue | 8 |
| Wild | — | none | 4 |
| Wild Draw Four | — | none | 4 |
| **Total** | | | **108** |

---

## 2. Setup

1. Each player draws one card to pick the dealer. Whoever draws the highest number deals. Action cards count as zero.
2. The dealer shuffles and deals **7 cards** to each player.
3. The remaining cards are placed face down to form the **draw pile**.
4. The top card of the draw pile is turned face up to start the **discard pile**.
5. Play starts with the player to the dealer's left and moves **clockwise**.

### If the first face-up card is an action card

| First card | Effect |
|------------|--------|
| Number card | Play starts normally. |
| Skip | The first player (dealer's left) is skipped. |
| Reverse | The dealer plays first, and play moves counter-clockwise. |
| Draw Two | The first player draws 2 cards and loses their turn. |
| Wild | The first player chooses the colour, then plays. |
| Wild Draw Four | It goes back into the deck, the deck is reshuffled, and a new card is turned up. |

---

## 3. Taking a turn

On your turn, play one card from your hand that matches the top discard by:
- **colour**, or
- **number**, or
- **symbol** (Skip on Skip, Reverse on Reverse, Draw Two on Draw Two), or
- play a **Wild** / **Wild Draw Four** (with restrictions below).

### If you don't play a card

- If you have no playable card, **or you choose not to play one**, draw **one** card from the draw pile.
- If that drawn card is playable, you may play it **immediately**.
- Otherwise your turn ends. You cannot play any other card from your hand that turn.

You play **only one card per turn**. There is no stacking: you can't play a Draw Two on top of a Draw Two to pass the penalty along.

### Empty draw pile

When the draw pile runs out, set the top discard aside, shuffle the rest of the discard pile into a new draw pile, and continue.

---

## 4. Action cards

| Card | Effect |
|------|--------|
| **Skip** | The next player loses their turn. |
| **Reverse** | The direction of play flips. With **2 players**, Reverse acts like Skip, so you play again. |
| **Draw Two** | The next player draws 2 cards and loses their turn. |
| **Wild** | You choose the colour to continue with. You can play it at any time, even if you have other playable cards. |
| **Wild Draw Four** | You choose the colour. The next player draws 4 cards and loses their turn. **Restriction:** you may only play it if you have **no card matching the current colour**. You may still play it if you hold cards that match by number or symbol, or other Wilds. |

### Challenging a Wild Draw Four

The player hit by a Wild Draw Four may **challenge** it, claiming it was played illegally. If they do, the server checks the offender's hand itself and announces only the verdict. The hand is never shown to the challenger or anyone else.

| Result | Penalty |
|--------|---------|
| Guilty: the player held a card matching the current colour | The **offender** draws the 4 cards instead, and the challenger does not lose their turn. |
| Innocent: the play was legal | The **challenger** draws **6** cards (4 + 2 penalty) and loses their turn. |
| No challenge | The next player draws 4 and loses their turn. |

---

## 5. Calling "CUNO"

- When you play your **second-to-last card**, leaving one card in hand, you must call **"CUNO"**.
- If another player catches you **before the next player starts their turn**, you draw **2 cards** as a penalty.
- Once the next player has started their turn, you can no longer be penalised for that missed call.

---

## 6. Winning a round

- The round ends when a player plays their **last card**.
- If the last card is a **Draw Two** or **Wild Draw Four**, the next player still draws the cards. Those cards count toward the winner's score.

---

## 7. Scoring

The round winner scores points for every card left in the **other players'** hands:

| Card | Points |
|------|--------|
| Number cards (0–9) | Face value |
| Skip, Reverse, Draw Two | 20 |
| Wild, Wild Draw Four | 50 |

The first player to reach **500 points** wins the game.

---

## 8. Not included (house rules)

These are popular but **not** part of the standard rules, so Cuno leaves them out for now:

- **Stacking:** answering a Draw Two or Draw Four with another one to pass the penalty along.
- **Jump-in:** playing an identical card out of turn.
- **7-0:** swapping hands on a 7, or passing hands on a 0.
- **Draw until you can play:** standard rules draw exactly one card.
- **Forced play:** standard rules let you draw even when you hold a playable card.

---

## 9. Online adaptations

These rules have no face-to-face equivalent online, so Cuno has to define them. They are proposals, not settled:

- **Choosing the dealer:** the server picks one at random instead of having everyone draw a card.
- **Calling CUNO:** a button you press while (or right after) playing your second-to-last card. Other players get a "Catch!" button that stays active until the next player acts. The server decides who was first.
- **Challenge window:** after a Wild Draw Four, the victim is offered Challenge / Accept, and the server reveals the hand only to the challenger.
- **Turn timer:** if a player doesn't act in time, they automatically draw and pass.
- **Disconnects:** a disconnected player keeps their seat and hand. Their turns are auto-passed until they reconnect.
