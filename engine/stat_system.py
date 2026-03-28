from dataclasses import dataclass, field

MAX_DELTA = 5


@dataclass
class Stat:
    name: str
    current_value: int
    min_val: int
    max_val: int
    checkpoints: list[int]
    display_name: str = ""


def get_tier(stat: Stat) -> int:
    """
    Returns which checkpoint tier the stat is currently in (0-indexed).
    Tier 0: below first checkpoint
    Tier 1: at or above first checkpoint but below second
    Tier 2: at or above second checkpoint, etc.
    """
    tier = 0
    for cp in sorted(stat.checkpoints):
        if stat.current_value >= cp:
            tier += 1
        else:
            break
    return tier


def apply_delta(stat: Stat, delta: int) -> tuple[int, int, int]:
    """
    Apply a stat change. Delta is clamped to [-MAX_DELTA, +MAX_DELTA].
    Mutates stat.current_value in place.
    Returns (new_value, old_tier, new_tier).
    """
    delta = max(-MAX_DELTA, min(MAX_DELTA, delta))
    old_tier = get_tier(stat)
    new_value = max(stat.min_val, min(stat.max_val, stat.current_value + delta))
    stat.current_value = new_value
    new_tier = get_tier(stat)
    return new_value, old_tier, new_tier
