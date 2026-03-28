import anthropic

client = anthropic.Anthropic()

_NARRATOR_BASE = (
    "You are the narrator of a text-based mystery game set in a dim, strange stone room. "
    "Describe events in second person ('you'). "
    "Be atmospheric and grounded — do not invent new story elements beyond what you are given. "
    "Never use game-language like 'you can't do that' or refer to stats, actions, or systems."
)


def narrate_opening(opening_text: str) -> str:
    """
    Render the story's opening narration. Passed straight through — no LLM needed.
    The opening text is authored, so we trust it as-is.
    """
    return opening_text


def narrate_consequence(consequence: str, player_message: str) -> str:
    """
    Narrate the consequence of a triggered action that has no NPC involved
    (pure environment interaction). Flavours the authored consequence text.
    """
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=(
            f"{_NARRATOR_BASE} "
            "Describe what happens as a result of the player's action. "
            "Stay close to the provided consequence — you are adding atmosphere, "
            "not new information. Keep it to 2–4 sentences."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f'The player said: "{player_message}"\n\n'
                    f"What happens:\n{consequence}"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def narrate_no_effect(player_message: str) -> str:
    """
    Respond to a player action that matched nothing in the game world.
    Should feel natural and in-world — not an error message.
    """
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=(
            f"{_NARRATOR_BASE} "
            "The player has just done or said something with no meaningful effect. "
            "Describe the stillness, the lack of result, or the room's indifference. "
            "Vary your phrasing — do not repeat the same line. "
            "1–2 sentences only."
        ),
        messages=[
            {
                "role": "user",
                "content": f'The player said: "{player_message}"',
            }
        ],
    )
    return response.content[0].text.strip()


def narrate_checkpoint_crossed(
    npc_name: str, old_tier: int, new_tier: int
) -> str:
    """
    Something has shifted in the player's relationship with an NPC.
    Narrate it subtly — felt, not stated.
    """
    direction = "warmed" if new_tier > old_tier else "cooled"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=(
            f"{_NARRATOR_BASE} "
            "Something has shifted between the player and an NPC. "
            "Describe it as a subtle change — a shift in bearing, a quality in the air, "
            "something felt rather than named. "
            "Do not mention trust, stats, or tiers. 1–2 sentences."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"The relationship with {npc_name} has {direction}. "
                    "Something is different now."
                ),
            }
        ],
    )
    return response.content[0].text.strip()
