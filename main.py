import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from agents import classifier, game_master
from agents import npc as npc_agent
from engine import backend
from engine.game_state import load_state, reset_state, save_state

# Max conversation exchanges kept in context per NPC (each exchange = 1 user + 1 assistant turn)
HISTORY_WINDOW = 10

# ---------------------------------------------------------------------------
# Terminal output helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"


def print_narrator(text: str) -> None:
    print(f"\n{text}\n")


def print_npc(name: str, text: str) -> None:
    print(f"\n{CYAN}{BOLD}{name}{RESET}{CYAN}: {text}{RESET}\n")


def print_system(text: str) -> None:
    print(f"{DIM}  [{text}]{RESET}")


def print_stat_change(display_name: str, new_value: int, delta: int) -> None:
    if delta == 0:
        return
    sign = "+" if delta > 0 else ""
    color = GREEN if delta > 0 else YELLOW
    print(f"{DIM}  {display_name}: {new_value} ({color}{sign}{delta}{RESET}{DIM}){RESET}")


def print_divider() -> None:
    print("─" * 60)


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------

def run(story_id: str) -> None:
    graph, characters, config = backend.load_story(story_id)
    state = load_state(story_id, config)

    # Per-NPC conversation history: plain text turns only (no tool call blocks)
    npc_histories: dict[str, list[dict]] = {npc_id: [] for npc_id in characters}
    # Track which NPCs have spoken for the first time this session
    introduced: set[str] = set()

    # Fire auto-triggered nodes (node 0 — game start)
    start_consequences = backend.auto_trigger_nodes(graph, state)
    save_state(state)

    # Opening screen
    print("\n" + "═" * 60)
    print(f"  {BOLD}{config['title'].upper()}{RESET}")
    print("═" * 60)
    print_narrator(config["opening_narration"])
    for c in start_consequences:
        print_narrator(c)
    print(f'{DIM}  Type "quit" to exit  |  "stats" to check stats  |  "reset" to restart{RESET}\n')
    print_divider()

    while True:
        # ── Win check ──────────────────────────────────────────────────────
        if backend.check_win(state, config):
            print_narrator(config["win_narration"])
            print("\n" + "═" * 60)
            print(f"  {BOLD}YOU ESCAPED{RESET}")
            print("═" * 60 + "\n")
            break

        # ── Player input ───────────────────────────────────────────────────
        try:
            player_input = input(f"\n{GREEN}>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFarewell.\n")
            break

        if not player_input:
            continue

        # ── Special commands ───────────────────────────────────────────────
        cmd = player_input.lower()

        if cmd == "quit":
            print("\nFarewell.\n")
            break

        if cmd == "reset":
            reset_state(story_id)
            print("\nRestarting...\n")
            run(story_id)
            return

        if cmd == "stats":
            for stat_name, value in state.stats.items():
                display = config["stats"][stat_name].get("display_name", stat_name)
                print_system(f"{display}: {value}")
            continue

        # ── Classify player input ──────────────────────────────────────────
        available = backend.get_available_action_descriptions(graph, state)
        action_id = classifier.classify(available, player_input)

        if action_id == "no_match":
            response = game_master.narrate_no_effect(player_input)
            print_narrator(response)
            continue

        # ── Process matched action ─────────────────────────────────────────
        result = backend.process_action(graph, state, action_id)
        save_state(state)

        triggers_npc = result["triggers_npc"]
        consequence   = result["consequence"]

        # ── NPC interaction ────────────────────────────────────────────────
        if triggers_npc:
            npc_id   = triggers_npc
            npc_data = characters[npc_id]

            # First time the NPC speaks — show their introduction line
            if npc_id not in introduced:
                introduced.add(npc_id)
                print_narrator(npc_data["introduction"])

            persona_info = backend.get_npc_persona(characters, npc_id, state)
            stat_name    = npc_data["stat"]
            history      = npc_histories[npc_id]

            npc_result = npc_agent.respond(
                npc_data=npc_data,
                persona=persona_info["persona"],
                stat_name=stat_name,
                consequence=consequence,
                history=history,
                player_message=player_input,
            )

            # Apply stat change (backend clamps ±5 again as a safeguard)
            stat_result = backend.apply_stat_change(
                state, config, stat_name, npc_result["delta"]
            )
            save_state(state)

            # Output NPC dialogue
            print_npc(npc_data["name"], npc_result["dialogue"])

            # Show stat change indicator
            print_stat_change(
                stat_result["display_name"],
                stat_result["new_value"],
                stat_result["delta_applied"],
            )

            # Checkpoint narration if a tier was crossed
            if stat_result["checkpoint_crossed"]:
                checkpoint_text = game_master.narrate_checkpoint_crossed(
                    npc_data["name"],
                    stat_result["old_tier"],
                    stat_result["new_tier"],
                )
                print_narrator(checkpoint_text)

            # Append to history (plain text, windowed)
            history.append({"role": "user",      "content": player_input})
            history.append({"role": "assistant", "content": npc_result["dialogue"]})
            if len(history) > HISTORY_WINDOW * 2:
                history[:] = history[-(HISTORY_WINDOW * 2):]

        # ── Environment action (GM narrates) ───────────────────────────────
        else:
            if consequence:
                narration = game_master.narrate_consequence(consequence, player_input)
                print_narrator(narration)

            # If this action spawns an NPC, show their introduction immediately
            for npc_id, npc_data in characters.items():
                if npc_data.get("spawned_by_action") == action_id and npc_id not in introduced:
                    introduced.add(npc_id)
                    print_narrator(npc_data["introduction"])

        print_divider()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Game Engine")
    parser.add_argument("--story", required=True, help="Story ID to load (e.g. escape_room)")
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe saved progress and start the story from scratch"
    )
    args = parser.parse_args()

    if args.reset:
        reset_state(args.story)
        print(f"Progress reset for '{args.story}'.")

    run(args.story)


if __name__ == "__main__":
    main()
