import anthropic

client = anthropic.Anthropic()

_CLASSIFY_TOOL = {
    "name": "classify_action",
    "description": "Report which action the player's message matches, or no_match if none fits.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_id": {
                "description": (
                    "The matched action ID as an integer, "
                    "or the string 'no_match' if nothing matches."
                ),
                "oneOf": [
                    {"type": "integer"},
                    {"type": "string", "enum": ["no_match"]},
                ],
            }
        },
        "required": ["action_id"],
    },
}

_SYSTEM = """\
You are a game action classifier. Your only job is to determine whether the \
player's message matches one of the available actions listed.

Rules:
- Match on intent and meaning, not exact wording. \
  "I check the table" and "What's on the table?" both match \
  "The player examines the table."
- Only match actions from the provided list. Do not invent actions.
- If the message could match multiple actions, pick the closest match.
- If nothing matches, return no_match.
- You MUST call the classify_action tool. Do not respond with plain text.\
"""


def classify(available_actions: list[dict], player_message: str) -> int | str:
    """
    Returns an action_id (int) if the player's message matches an available
    action, or the string "no_match" if nothing fits.
    """
    if not available_actions:
        return "no_match"

    action_list = "\n".join(
        f"- action {a['id']}: {a['description']}" for a in available_actions
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        temperature=0,
        system=_SYSTEM,
        tools=[_CLASSIFY_TOOL],
        tool_choice={"type": "any"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Available actions:\n{action_list}\n\n"
                    f'Player message: "{player_message}"\n\n'
                    "Call classify_action with the matching action_id or \"no_match\"."
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "classify_action":
            return block.input["action_id"]

    return "no_match"
