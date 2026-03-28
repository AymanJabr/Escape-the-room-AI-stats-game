# LLM Game Engine

A framework that bridges traditional narrative game engines (Renpy, Twine) and AI chat experiences (SillyTavern, AI Dungeon).

The core idea: give players freedom to speak and act naturally, but enforce story progression and character stats through a deterministic backend the AI cannot override.

Inspired by [Jacky Kaub's causal graph approach](https://towardsdatascience.com/how-i-built-an-llm-based-game-from-scratch-86ac55ec7a10/).

---

## What makes this different

| Classical game (Twine/Renpy) | AI chat game (SillyTavern) | This engine |
|---|---|---|
| Full authorial control | Full player freedom | Controlled freedom |
| Deterministic outcomes | Anything goes | Bounded outcomes |
| No dynamic dialogue | Infinite dynamic dialogue | Dynamic dialogue, locked progression |
| Hand-crafted every line | No authored structure | Author the structure, AI fills the dialogue |

**The player can say anything. But only specific actions advance the story, and only honest interaction moves the stats.**

---

## How it works

The game is built around two interlocking systems:

### 1. Causal Graph
A directed graph of story nodes. Each node is an "impactful action" with:
- A **description** (used by the classifier to match player input)
- A **consequence** (revealed to the narrator only after the action triggers — no spoilers)
- **Prerequisites** (prior actions that must be done first)
- Optional **stat gates** (a stat must reach a threshold before this node is even available)

The player can say anything. A classifier agent silently checks if what they said matches an available action. If not, the game master tells them their action had no effect and the story doesn't advance.

### 2. Stat System
Characters have stats (e.g. `trust`, `love`, `suspicion`). After each NPC interaction, an agent evaluates the exchange and calls a `modify_stat` tool — but the tool schema enforces a hard cap of **±5 per interaction**. The backend clamps and validates this before applying it.

Stats have **checkpoints**. When a stat crosses a threshold, the NPC's persona changes and new causal graph branches unlock. The AI has no way to jump a stat from 0 to 100 — it can only move it 5 points at a time.

---

## What the player can and cannot do

| Player action | Result |
|---|---|
| Say something that matches an available action | Story advances, stat changes |
| Say something that doesn't match any action | "Your action has no effect" |
| Try to brute-force the story ("I win everything now") | Classified as no-match |
| Repeat an already-completed action | Filtered out, no re-trigger |
| Ask an NPC about something they shouldn't know yet | NPC's context literally doesn't contain it |

---

## Stories

Stories live in `stories/<story-name>/` and consist of three JSON files:

- `graph.json` — the causal graph
- `characters.json` — NPC definitions with stat-gated personas
- `config.json` — story settings (which stats exist, starting values, etc.)

### Current stories
- **escape_room** — based on Jacky Kaub's mystery room. Player is locked in a room and must find the exit. The ghost NPC has a `trust` stat that gates how useful its hints are.

---

## Stack

- **Language**: Python 3.11+
- **LLM**: Claude Haiku (via Anthropic API) — fast and cheap for the classifier loop
- **State**: JSON files (no database)
- **Interface**: Terminal

---

## Setup

```bash
pip install -r requirements.txt
```

Copy the example env file and add your key:
```bash
cp .env.example .env
# then open .env and replace "your-key-here" with your actual ANTHROPIC_API_KEY
```

Run the game:
```bash
python main.py --story escape_room
```

To wipe progress and restart:
```bash
python main.py --story escape_room --reset
```

---

## Project structure

```
├── engine/
│   ├── causal_graph.py     # Graph filtering and unlock logic
│   ├── game_state.py       # State persistence
│   ├── stat_system.py      # Stat bounds, checkpoints
│   └── backend.py          # Orchestrates all engine components
├── agents/
│   ├── classifier.py       # Matches player input to available actions
│   ├── npc.py              # NPC agent with stat-gated persona + modify_stat tool
│   └── game_master.py      # Narrates consequences and non-events
├── stories/
│   └── escape_room/
│       ├── graph.json
│       ├── characters.json
│       └── config.json
├── state/                  # Runtime state (gitignored)
├── ARCHITECTURE.md
├── PLAN.md
└── README.md
```
