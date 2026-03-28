import anthropic

client = anthropic.Anthropic()

_MODIFY_STAT_TOOL = {
    "name": "modify_stat",
    "description": (
        "Adjust a character stat based on the quality of this interaction. "
        "You MUST call this tool once per response — your turn is not complete without it. "
        "Be honest: reflect how the player's message genuinely affected your character."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "stat_name": {
                "type": "string",
                "description": "The name of the stat to modify.",
            },
            "delta": {
                "type": "integer",
                "minimum": -5,
                "maximum": 5,
                "description": (
                    "How much to change the stat. Must be between -5 and +5.\n"
                    "+4 to +5: genuinely moving or impressive\n"
                    "+1 to +3: positive, friendly, thoughtful\n"
                    "0: neutral exchange\n"
                    "-1 to -3: rude, dismissive, unwelcome\n"
                    "-4 to -5: hostile or deeply offensive"
                ),
            },
            "reason": {
                "type": "string",
                "description": "One sentence explaining why you chose this delta.",
            },
        },
        "required": ["stat_name", "delta", "reason"],
    },
}


def _build_system(npc_name: str, persona: dict, stat_name: str, consequence: str | None) -> str:
    parts = [
        f"You are {npc_name}.",
        "",
        persona["personality"],
        "",
        f"After each response you MUST call the modify_stat tool with stat_name='{stat_name}'.",
        "The delta should honestly reflect how the player's words or actions affected you.",
        "",
        "Stay in character at all times. Do not break the fourth wall.",
        "Keep responses to 2–4 sentences unless the moment clearly calls for more.",
    ]
    if consequence:
        parts.insert(2, f"[Scene context: {consequence}]")
    return "\n".join(parts)


def respond(
    npc_data: dict,
    persona: dict,
    stat_name: str,
    consequence: str | None,
    history: list[dict],
    player_message: str,
    max_retries: int = 2,
) -> dict:
    """
    Generate an NPC response and a stat delta via tool call.

    history is a plain list of {"role": "user"|"assistant", "content": str}
    representing prior exchanges in this session (tool calls stripped out
    so we never have to manage tool_result turns in history).

    Returns {"dialogue": str, "delta": int, "reason": str}.
    """
    npc_name = npc_data["name"]
    system = _build_system(npc_name, persona, stat_name, consequence)

    messages = list(history)
    messages.append({"role": "user", "content": player_message})

    dialogue = ""
    delta = 0
    reason = ""

    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tools=[_MODIFY_STAT_TOOL],
            messages=messages,
        )

        tool_found = False
        current_dialogue = ""

        for block in response.content:
            if block.type == "text":
                current_dialogue += block.text
            elif block.type == "tool_use" and block.name == "modify_stat":
                delta = max(-5, min(5, int(block.input.get("delta", 0))))
                reason = block.input.get("reason", "")
                tool_found = True

        dialogue = current_dialogue.strip()

        if tool_found:
            return {"dialogue": dialogue, "delta": delta, "reason": reason}

        # Tool wasn't called — append the assistant turn and nudge
        if attempt < max_retries:
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": (
                    f"You must call the modify_stat tool with stat_name='{stat_name}' "
                    "to complete your turn."
                ),
            })

    # All retries exhausted — return what we have with a neutral delta
    return {"dialogue": dialogue or "...", "delta": 0, "reason": "tool call failed"}
