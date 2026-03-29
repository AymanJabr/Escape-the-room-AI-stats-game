from dataclasses import dataclass, field


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


def get_tier_bounds(stat_config: dict, tier: int) -> tuple[int, int]:
    """
    Returns (min_delta, max_delta) for the given tier.
    Reads from the stat config's tier_bounds list.
    Falls back to ±5 if tier_bounds is not defined.
    """
    for tb in stat_config.get("tier_bounds", []):
        if tb["tier"] == tier:
            return tb["min_delta"], tb["max_delta"]
    return -5, 5


def apply_delta(
    stat: Stat, delta: int, min_delta: int = -5, max_delta: int = 5
) -> tuple[int, int, int]:
    """
    Apply a stat change clamped to [min_delta, max_delta].
    Mutates stat.current_value in place.
    Returns (new_value, old_tier, new_tier).
    """
    delta = max(min_delta, min(max_delta, delta))
    old_tier = get_tier(stat)
    new_value = max(stat.min_val, min(stat.max_val, stat.current_value + delta))
    stat.current_value = new_value
    new_tier = get_tier(stat)
    return new_value, old_tier, new_tier
