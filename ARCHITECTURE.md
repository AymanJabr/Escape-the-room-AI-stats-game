# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         PLAYER                                  │
│                  types a message / action                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND                                    │
│  filter_game_state()                                            │
│  Reads game_state.json → builds list of currently available    │
│  action descriptions (excludes done actions, stat-gated nodes  │
│  the player hasn't unlocked, and future spoiler content)       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              available action descriptions
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLASSIFIER AGENT (Haiku)                      │
│                                                                 │
│  System: "Given this list of available actions, does the        │
│  player's message match any of them? Return action_id or        │
│  'no_match'."                                                   │
│                                                                 │
│  Input:  available action descriptions + player message         │
│  Output: action_id | "no_match"                                 │
└────────────┬──────────────────────────────┬─────────────────────┘
             │                              │
          no_match                       action_id
             │                              │
             ▼                              ▼
┌────────────────────┐     ┌────────────────────────────────────┐
│  GAME MASTER AGENT │     │  BACKEND                           │
│                    │     │  get_action_consequence(action_id) │
│  "Your action has  │     │  → fetches consequence text        │
│  no effect here."  │     │  update_game_state(action_id)      │
│                    │     │  → marks action as completed       │
│  Responds in-world │     │  → checks for newly unlocked nodes │
│  to the player     │     └──────────────┬─────────────────────┘
└────────────────────┘                    │
             │                 consequence + updated context
             │                            │
             │                            ▼
             │           ┌────────────────────────────────────────┐
             │           │          NPC AGENT (Haiku)             │
             │           │                                        │
             │           │  System prompt includes:               │
             │           │  - NPC persona for CURRENT stat tier   │
             │           │  - consequence of the triggered action │
             │           │  - conversation history (windowed)     │
             │           │                                        │
             │           │  Only tool available:                  │
             │           │  modify_stat(stat, delta ∈ [-5, +5])   │
             │           │                                        │
             │           │  Agent MUST call modify_stat before    │
             │           │  its response is accepted              │
             │           └──────────────┬─────────────────────────┘
             │                          │
             │              tool call: modify_stat(delta)
             │                          │
             │                          ▼
             │           ┌────────────────────────────────────────┐
             │           │  BACKEND: apply_stat_change()          │
             │           │  - clamps delta to [-5, +5]            │
             │           │  - applies to game_state.json          │
             │           │  - checks if stat crossed a checkpoint │
             │           │    → if yes: update NPC persona tier   │
             │           │    → if yes: unlock new graph nodes    │
             │           └──────────────┬─────────────────────────┘
             │                          │
             └──────────────────────────┘
                                        │
                                        ▼
                              Output to player terminal
```

---

## Stat System Detail

Stats have named checkpoints. A stat never jumps more than 5 points in one interaction.

```
TRUST stat (Ghost NPC — escape room)

  0 ─────────────── 20 ─────────────── 50 ─────────────── 100
  │                  │                  │                   │
  Tier 0             Tier 1             Tier 2
  "cryptic,          "gives cryptic     "speaks plainly,
  speaks in          digit hints,       reveals full
  riddles only"      withholds order"   code on request"

Tier 0: delta ∈ [-5, +5]
Tier 1: delta ∈ [-3, +10]
Tier 2: delta ∈ [-2, +15]
Crossing 20 → persona switches, stat-gated graph nodes unlock
```

When a checkpoint is crossed:
1. NPC persona string is swapped in the next system prompt
2. Causal graph re-filtered: nodes with `stat_gates: {"trust": 20}` now appear in the classifier's available action list

---

## Causal Graph Detail

```
Node schema (graph.json):

{
  "id": 4,
  "name": "read_note",
  "description": "The player reads the note on the table",   ← classifier sees this
  "consequence": "The air grows cold and the lights...",     ← only revealed on trigger
  "needs": [0],                                              ← prerequisite action IDs
  "stat_gates": { "trust": 20 },                            ← optional stat threshold
  "triggers_npc": "ghost"                                   ← optional: which NPC responds
}
```

**Information firewall:**
- Classifier agent sees ONLY `description` fields of available nodes
- NPC/GM agent sees ONLY the `consequence` of the just-triggered node
- No agent ever receives the full graph — only what the backend decides to pass

```
Full graph.json
      │
      │  filter_game_state()
      │  ─ remove completed action IDs
      │  ─ remove nodes whose `needs` aren't met
      │  ─ remove nodes whose `stat_gates` aren't met
      │
      ▼
Available actions (descriptions only)
      │
      │  on trigger: get_action_consequence(id)
      │
      ▼
Consequence text (for this node only)
```

---

## Data Flow (files)

```
stories/escape_room/
  graph.json          ← read-only at runtime, authored by game designer
  characters.json     ← read-only at runtime
  config.json         ← read-only at runtime

state/
  game_state.json     ← read/write at runtime
    {
      "story": "escape_room",
      "completed_actions": [0, 1, 3],
      "stats": { "trust": 22 },
      "active_persona": { "ghost": 1 }
    }
```

---

## Agent Prompting Strategy

### Classifier Agent
- Receives only action descriptions, never consequences
- Returns a structured response (action_id int or string "no_match")
- Low temperature — this is a classification task, not creative writing
- Uses tool call to return result cleanly

### NPC Agent
- Receives: persona string for current stat tier + triggered consequence + recent history
- Has exactly one tool: `modify_stat`
- Instructed to always call `modify_stat` before completing its turn
- The delta should reflect the quality of the player's interaction honestly
- Medium temperature — character dialogue, some creativity

### Game Master Agent
- Handles "no_match" cases and scene narration
- Does NOT have access to `modify_stat`
- Keeps player grounded in the world ("your action has no effect") without being dismissive
- Also handles consequence narration when there's no NPC involved (environment interactions)
- On "no_match", receives a **discovered-state context**: a summary of everything the player has already found (built from completed nodes' consequence text). This prevents the GM from contradicting visible objects or saying "nothing new" when unexplored things are still present.

---

## What the AI cannot do

| Attempted abuse | Why it fails |
|---|---|
| Skip ahead in the story | Consequence text is never in context until triggered |
| Reveal future secrets | Full graph never passed to any agent |
| Give +50 love in one message | Tool schema rejects delta > tier max; backend clamps anyway |
| Re-trigger a completed action | Filtered out of available actions list |
| Ignore stat gates | Backend enforces — node never appears in classifier context |
| Pretend a stat is higher | Stats only come from game_state.json, not from model |
| Say "nothing is here" when objects exist | GM receives discovered-state context grounding it in found objects |
