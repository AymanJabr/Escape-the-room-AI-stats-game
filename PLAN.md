# Implementation Plan

## Milestone 0 — Story Data (no code)
Author the escape room story files before writing any engine code.
Working data lets us test the engine against something real immediately.

- [ ] `stories/escape_room/config.json` — stat definitions, starting values, story metadata
- [ ] `stories/escape_room/graph.json` — causal graph (nodes from Jacky's escape room + ghost interactions)
- [ ] `stories/escape_room/characters.json` — Ghost NPC with trust-gated persona tiers

---

## Milestone 1 — Engine Core (no AI)
Pure Python, deterministic. No API calls. Fully unit-testable.

- [ ] `engine/stat_system.py`
  - `Stat` dataclass: name, current value, min, max, checkpoints list
  - `apply_delta(stat, delta) -> (new_value, checkpoint_crossed: bool)`
  - `get_tier(stat) -> int` — which checkpoint tier the stat is currently in
  - Hard clamp: delta is always clamped to [-5, +5] regardless of input

- [ ] `engine/causal_graph.py`
  - `load_graph(story_path) -> list[Node]`
  - `get_available_actions(graph, game_state) -> list[Node]`
    - filters out completed nodes
    - filters out nodes whose `needs` aren't in completed_actions
    - filters out nodes whose `stat_gates` aren't met
  - `get_consequence(graph, action_id) -> str`
  - `Node` dataclass

- [ ] `engine/game_state.py`
  - `load_state(story) -> GameState`
  - `save_state(state)`
  - `mark_action_complete(state, action_id)`
  - `update_stat(state, stat_name, delta) -> checkpoint_crossed: bool`
  - `GameState` dataclass: completed_actions, stats, active_personas

- [ ] `engine/backend.py`
  - `filter_game_state(graph, state) -> list[ActionDescription]` — descriptions only
  - `get_action_consequence(graph, action_id) -> str`
  - `update_game_state(state, action_id)`
  - `apply_stat_change(state, characters, stat_name, delta) -> dict` — returns new value, tier change if any
  - `get_npc_persona(characters, npc_id, state) -> str` — current persona string

---

## Milestone 2 — Agents
Each agent is a thin wrapper: builds a prompt, calls Haiku, parses output.

- [ ] `agents/classifier.py`
  - Input: available action descriptions + player message
  - Uses tool call to return `{"action_id": int}` or `{"action_id": "no_match"}`
  - Low temperature (0.0–0.2)
  - No story content beyond action descriptions

- [ ] `agents/npc.py`
  - Input: NPC persona string + consequence text + conversation history
  - Tool: `modify_stat` with `delta` constrained to `minimum: -5, maximum: 5` in schema
  - Agent must call the tool — loop until it does (max 2 retries)
  - Returns: NPC dialogue text + validated delta

- [ ] `agents/game_master.py`
  - Input: player message + context (no_match or consequence narration)
  - No tools
  - Handles both: "no effect" responses and scene consequence narration

---

## Milestone 3 — Game Loop

- [ ] `main.py`
  - Argument: `--story <name>`
  - Init: load story config, load or create game state
  - Loop:
    1. Print prompt, read player input
    2. `filter_game_state` → available actions
    3. `classifier.classify(actions, player_input)` → action_id or no_match
    4. If no_match → `game_master.narrate_no_effect(player_input)` → print, loop
    5. If match → `backend.get_action_consequence(action_id)`
    6. `backend.update_game_state(action_id)`
    7. Determine if NPC triggered or GM narrates
    8. If NPC → `npc.respond(persona, consequence, history)` → gets delta via tool
    9. `backend.apply_stat_change(delta)` → check checkpoint
    10. If checkpoint crossed → print tier-change narration, update personas
    11. Print NPC/GM response, append to history
    12. Check win condition (specific action_id completed)

---

## Milestone 4 — Polish & Testing

- [ ] Manual playtest of the full escape room
- [ ] Edge cases: stat at exactly a checkpoint boundary, all actions completed, ghost at max trust
- [ ] Prompt tuning: classifier accuracy, NPC persona consistency, GM "no effect" variety
- [ ] `.gitignore` for `state/` directory
- [ ] `requirements.txt`

---

## Story: Escape Room (Jacky Kaub base + Ghost trust stat)

### Causal Graph Overview

```
[0] Game Start (auto-triggered)
 ├── [1] Inspect the room (needs: 0)
 │    ├── [2] Find the note on the table (needs: 1)
 │    │    └── [4] Read the note → spawns Ghost (needs: 2)
 │    └── [3] Find the painting on the wall (needs: 1)
 │         └── [5] Inspect the painting → reveals hidden button (needs: 3)
 ├── [6] Ask Ghost for help (needs: 4, stat_gate: trust >= 0)
 │    └── [7] Ask Ghost about the button (needs: 4,5, stat_gate: trust >= 20)
 │         └── [8] Ask Ghost the escape code (needs: 7, stat_gate: trust >= 50)
 └── [9] Push the button (needs: 5)
      └── [10] Enter the code (needs: 8,9) ← WIN CONDITION
```

Ghost trust tiers:
- **0–19**: Cryptic. Speaks in riddles. Won't answer direct questions.
- **20–49**: Reluctant. Vague directions. References the button.
- **50+**: Cooperative. Will reveal the code if asked directly.

### Win Condition
Action 10 "Enter the code" completes → game master prints ending scene → exit.

---

## Notes & Decisions

- Conversation history passed to NPC agent is **windowed** (last N exchanges) to keep context small and avoid the model drifting from the current scene
- The classifier sees **only descriptions**, never consequences — this is the anti-spoiler firewall
- `modify_stat` tool delta range is enforced at two levels: JSON schema (model-side) and backend clamp (server-side). Belt and suspenders.
- Ghost is the only NPC in v1. The stat system is designed generically so adding more characters (each with their own stat) requires only data changes, not code changes.
