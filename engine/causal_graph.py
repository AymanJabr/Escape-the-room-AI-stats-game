import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Node:
    id: int
    name: str
    description: str
    consequence: Optional[str]
    needs: list[int]
    repeatable: bool
    triggers_npc: Optional[str]
    auto_trigger: bool
    stat_gates: dict[str, int] = field(default_factory=dict)


def load_graph(story_path: Path) -> list[Node]:
    with open(story_path / "graph.json") as f:
        data = json.load(f)
    return [
        Node(
            id=n["id"],
            name=n["name"],
            description=n["description"],
            consequence=n.get("consequence"),
            needs=n.get("needs", []),
            repeatable=n.get("repeatable", False),
            triggers_npc=n.get("triggers_npc"),
            auto_trigger=n.get("auto_trigger", False),
            stat_gates=n.get("stat_gates", {}),
        )
        for n in data
    ]


def get_available_actions(
    graph: list[Node], completed: set[int], stats: dict[str, int]
) -> list[Node]:
    """
    Returns nodes the player can currently act on:
    - not already completed (unless repeatable)
    - all prerequisite actions are done
    - all stat gates are met
    - not auto-triggered (those fire silently in the backend)
    """
    available = []
    for node in graph:
        if node.auto_trigger:
            continue
        if not node.repeatable and node.id in completed:
            continue
        if not all(req in completed for req in node.needs):
            continue
        if not all(stats.get(stat, 0) >= threshold for stat, threshold in node.stat_gates.items()):
            continue
        available.append(node)
    return available


def get_node(graph: list[Node], action_id: int) -> Optional[Node]:
    for node in graph:
        if node.id == action_id:
            return node
    return None
