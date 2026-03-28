import json
from pathlib import Path
from typing import Optional

from engine.causal_graph import Node, get_available_actions, get_node, load_graph
from engine.game_state import GameState, mark_action_complete, save_state
from engine.stat_system import Stat, apply_delta, get_tier

STORIES_DIR = Path(__file__).parent.parent / "stories"


# ---------------------------------------------------------------------------
# Story loading
# ---------------------------------------------------------------------------

def load_story(story_id: str) -> tuple[list[Node], dict, dict]:
    """Load and return (graph, characters, config) for a given story."""
    path = STORIES_DIR / story_id
    graph = load_graph(path)
    with open(path / "characters.json") as f:
        characters = json.load(f)
    with open(path / "config.json") as f:
        config = json.load(f)
    return graph, characters, config


# ---------------------------------------------------------------------------
# Causal graph helpers
# ---------------------------------------------------------------------------

def get_available_action_descriptions(
    graph: list[Node], state: GameState
) -> list[dict]:
    """
    Returns id + description pairs for the classifier agent.
    Consequences are never included here — that is the information firewall.
    """
    available = get_available_actions(graph, state.completed_actions, state.stats)
    return [{"id": n.id, "description": n.description} for n in available]


def process_action(
    graph: list[Node], state: GameState, action_id: int
) -> dict:
    """
    Mark a non-repeatable action as complete and return its consequence text
    and which NPC (if any) should respond.
    Does NOT apply stat changes — that is the NPC agent's responsibility.
    """
    node = get_node(graph, action_id)
    if node is None:
        return {"consequence": None, "triggers_npc": None, "node": None}

    if not node.repeatable:
        mark_action_complete(state, action_id)

    return {
        "consequence": node.consequence,
        "triggers_npc": node.triggers_npc,
        "node": node,
    }


def auto_trigger_nodes(graph: list[Node], state: GameState) -> list[str]:
    """
    Fire any nodes marked auto_trigger whose prerequisites are met.
    Used at game start (node 0) and after state changes.
    Returns a list of consequence strings to display.
    """
    consequences = []
    for node in graph:
        if node.auto_trigger and node.id not in state.completed_actions:
            if all(req in state.completed_actions for req in node.needs):
                mark_action_complete(state, node.id)
                if node.consequence:
                    consequences.append(node.consequence)
    return consequences


# ---------------------------------------------------------------------------
# Stat helpers
# ---------------------------------------------------------------------------

def apply_stat_change(
    state: GameState, config: dict, stat_name: str, delta: int
) -> dict:
    """
    Apply a bounded stat delta from the NPC agent's tool call.
    Returns a result dict with old/new values and whether a checkpoint was crossed.
    """
    stat_config = config["stats"][stat_name]
    stat = Stat(
        name=stat_name,
        current_value=state.stats[stat_name],
        min_val=stat_config["min"],
        max_val=stat_config["max"],
        checkpoints=stat_config["checkpoints"],
        display_name=stat_config.get("display_name", stat_name),
    )
    old_value = stat.current_value
    old_tier = get_tier(stat)
    new_value, _, new_tier = apply_delta(stat, delta)
    state.stats[stat_name] = new_value

    return {
        "stat": stat_name,
        "display_name": stat.display_name,
        "old_value": old_value,
        "new_value": new_value,
        "delta_applied": new_value - old_value,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "checkpoint_crossed": new_tier != old_tier,
    }


# ---------------------------------------------------------------------------
# NPC helpers
# ---------------------------------------------------------------------------

def get_npc_persona(characters: dict, npc_id: str, state: GameState) -> dict:
    """
    Returns the NPC data dict and the currently active persona tier
    based on the relevant stat's current value.
    """
    npc = characters[npc_id]
    stat_value = state.stats.get(npc["stat"], 0)
    current_persona = npc["personas"][0]
    for persona in npc["personas"]:
        if stat_value >= persona["min"]:
            current_persona = persona
    return {
        "npc": npc,
        "persona": current_persona,
        "stat_value": stat_value,
        "tier": current_persona["tier"],
    }


def is_npc_spawned(characters: dict, npc_id: str, state: GameState) -> bool:
    """Returns True if the action that spawns this NPC has been completed."""
    npc = characters.get(npc_id, {})
    spawn_action = npc.get("spawned_by_action")
    if spawn_action is None:
        return True  # always present if no spawn action defined
    return spawn_action in state.completed_actions


# ---------------------------------------------------------------------------
# Win condition
# ---------------------------------------------------------------------------

def check_win(state: GameState, config: dict) -> bool:
    return config["win_action_id"] in state.completed_actions
