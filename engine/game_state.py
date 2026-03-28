import json
from dataclasses import dataclass, field
from pathlib import Path

STATE_DIR = Path(__file__).parent.parent / "state"


@dataclass
class GameState:
    story_id: str
    completed_actions: set[int] = field(default_factory=set)
    stats: dict[str, int] = field(default_factory=dict)
    # Tracks which persona tier each NPC is currently on, so we can detect changes
    active_persona_tiers: dict[str, int] = field(default_factory=dict)


def load_state(story_id: str, config: dict) -> GameState:
    """Load saved state, or create a fresh one from story config defaults."""
    path = STATE_DIR / f"{story_id}.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        return GameState(
            story_id=data["story_id"],
            completed_actions=set(data["completed_actions"]),
            stats=data["stats"],
            active_persona_tiers=data["active_persona_tiers"],
        )
    # Fresh game: initialise stats from config starting values
    stats = {name: cfg["starting_value"] for name, cfg in config["stats"].items()}
    return GameState(story_id=story_id, stats=stats)


def save_state(state: GameState) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    path = STATE_DIR / f"{state.story_id}.json"
    data = {
        "story_id": state.story_id,
        "completed_actions": sorted(state.completed_actions),
        "stats": state.stats,
        "active_persona_tiers": state.active_persona_tiers,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def mark_action_complete(state: GameState, action_id: int) -> None:
    state.completed_actions.add(action_id)


def reset_state(story_id: str) -> None:
    """Delete saved state so the next load starts fresh."""
    path = STATE_DIR / f"{story_id}.json"
    if path.exists():
        path.unlink()
