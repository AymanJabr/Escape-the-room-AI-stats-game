import anthropic

client = anthropic.Anthropic()


def _build_tool(stat_name: str, min_delta: int, max_delta: int) -> dict:
    """Build the modify_stat tool with bounds matching the current tier."""
    high = max_delta
    low = min_delta
    mid_pos = max(1, high // 2)
    mid_neg = min(-1, low // 2)

    description = (
        f"How much to change the stat. Must be between {low} and +{high}.\n"
        f"+{mid_pos} to +{high}: genuinely positive — the player moved or impressed you\n"
        f"+1 to +{mid_pos - 1}: friendly, thoughtful, or engaging\n"
        f"0: neutral exchange\n"
        f"{mid_neg + 1} to -1: rude, dismissive, or unwelcome\n"
        f"{low} to {mid_neg}: hostile or deeply offensive"
    )

    return {
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
                    "minimum": min_delta,
                    "maximum": max_delta,
                    "description": description,
                },
                "reason": {
                    "type": "string",
                    "description": "One sentence explaining why you chose this delta.",
                },
            },
            "required": ["stat_name", "delta", "reason"],
        },
    }


def _build_system(
    npc_name: str, persona: dict, stat_name: str,
    min_delta: int, max_delta: int, consequence: str | None
) -> str:
    parts = [
        f"You are {npc_name}.",
        "",
        persona["personality"],
        "",
        "IMPORTANT: Always write your in-character dialogue as text FIRST.",
        "Only call modify_stat AFTER you have written your response.",
        "A response with no text — only a tool call — is not acceptable.",
        "",
        f"After writing your response, call modify_stat with stat_name='{stat_name}'.",
        f"The delta must be between {min_delta} and +{max_delta}.",
        "It should honestly reflect how the player's words or actions affected you.",
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
    min_delta: int,
    max_delta: int,
    consequence: str | None,
    history: list[dict],
    player_message: str,
    max_retries: int = 2,
) -> dict:
    """
    Generate an NPC response and a stat delta via tool call.

    history is plain {"role", "content"} pairs — tool call blocks stripped out.
    Returns {"dialogue": str, "delta": int, "reason": str}.
    """
    npc_name = npc_data["name"]
    system = _build_system(npc_name, persona, stat_name, min_delta, max_delta, consequence)
    tool = _build_tool(stat_name, min_delta, max_delta)

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
            tools=[tool],
            messages=messages,
        )

        tool_found = False
        current_dialogue = ""

        for block in response.content:
            if block.type == "text":
                current_dialogue += block.text
            elif block.type == "tool_use" and block.name == "modify_stat":
                raw_delta = int(block.input.get("delta", 0))
                delta = max(min_delta, min(max_delta, raw_delta))
                reason = block.input.get("reason", "")
                tool_found = True

        dialogue = current_dialogue.strip()

        if tool_found:
            # Model called the tool but forgot to write dialogue — recover it
            if not dialogue:
                recovery = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    system=(
                        f"You are {npc_name}. {persona['personality']}\n\n"
                        "Write your in-character response to the player's message. "
                        "Text only — no tools."
                    ),
                    messages=[{"role": "user", "content": player_message}],
                )
                for block in recovery.content:
                    if block.type == "text":
                        dialogue = block.text.strip()
                        break
            return {"dialogue": dialogue or "...", "delta": delta, "reason": reason}

        # Tool wasn't called at all — nudge
        if attempt < max_retries:
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": (
                    f"You must call the modify_stat tool with stat_name='{stat_name}' "
                    "to complete your turn."
                ),
            })

    return {"dialogue": dialogue or "...", "delta": 0, "reason": "tool call failed"}
