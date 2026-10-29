"""Write Claude-Ojouchan's settings into AstrBot's cmd_config.json.

Runs on the VM before the container starts (see up.sh). Secrets come from the environment (Doppler):
the Discord token is written into the file, which only root can read; the Anthropic key stays an
environment reference that AstrBot resolves at load time. Every key set here is owned by this repo,
so a change made in the dashboard to one of them is overwritten on the next deploy.
"""

import json
import os
import sys
import tempfile

# Top-level cache_control turns on automatic prompt caching: the breakpoint follows the end of the
# conversation, so each call pays full price only for what is new since the previous one.
AUTO_CACHE = {"cache_control": {"type": "ephemeral"}}

ANTHROPIC = {
    "id": "anthropic",
    "provider": "anthropic",
    "type": "anthropic_chat_completion",
    "provider_type": "chat_completion",
    "enable": True,
    "key": ["$ANTHROPIC_API_KEY"],
    "api_base": "https://api.anthropic.com",
    "timeout": 120,
    "proxy": "",
    "custom_headers": {},
    "anth_thinking_config": {"type": "", "budget": 0, "effort": ""},
}

MODELS = [
    {
        # Main chat model. Low effort keeps adaptive thinking (billed as output) short.
        "id": "sonnet",
        "provider_source_id": "anthropic",
        "model": "claude-sonnet-5-5",
        "enable": True,
        "modalities": ["text", "image", "tool_use"],
        "anth_thinking_config": {"type": "adaptive", "budget": 0, "effort": "low"},
        "custom_extra_body": {**AUTO_CACHE, "max_tokens": 4096},
    },
    {
        # Cheap side tasks: deciding whether to speak, tidying memory.
        "id": "haiku",
        "provider_source_id": "anthropic",
        "model": "claude-haiku-5-5",
        "enable": True,
        "modalities": ["text", "image", "tool_use"],
        "anth_thinking_config": {"type": "adaptive", "budget": 0, "effort": "low"},
        "custom_extra_body": {**AUTO_CACHE, "max_tokens": 1024},
    },
]


def upsert(items, item):
    for index, existing in enumerate(items):
        if existing.get("id") == item["id"]:
            items[index] = {**existing, **item}
            return
    items.append(item)


def main(path):
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    owner = os.environ.get("OJOU_OWNER_ID", "")
    if not token or not owner or not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("DISCORD_BOT_TOKEN, OJOU_OWNER_ID and ANTHROPIC_API_KEY must be set (run through deploy/up.sh)")

    with open(path, encoding="utf-8-sig") as file:
        config = json.load(file)

    upsert(config.setdefault("provider_sources", []), ANTHROPIC)
    for model in MODELS:
        upsert(config.setdefault("provider", []), model)
    upsert(
        config.setdefault("platform", []),
        {
            "id": "discord",
            "type": "discord",
            "enable": True,
            "discord_token": token,
            "discord_proxy": "",
            "discord_command_register": True,
            "discord_activity_name": "",
            # Bot messages reach the plugin, which lets through only the bots in OJOU_FRIEND_BOTS.
            "discord_allow_bot_messages": True,
        },
    )

    runner = config["agent_runner"]["config"]
    runner["model"]["provider_id"] = "sonnet"
    # Her persona (plugins/ojou_core/persona.md, installed by the plugin) instead of AstrBot's
    # "helpful assistant"; AstrBot's extra safe-mode prompt is off at the owner's request.
    runner["persona"].update(persona_id="claude-ojousama", safety_mode=False)
    # Drop old turns in one large chunk instead of one at a time: every trim changes the start of the
    # conversation and costs one full-price read, so trimming rarely keeps the cache warm.
    runner["compression"].update(max_turns=40, trim_turns=15, overflow_strategy="truncate_by_turns")
    # A turn may call the model at most this many times (tool loops).
    runner["misc"]["max_steps"] = 12

    # Who is speaking and in which server; both go into the current message, after the cache breakpoint.
    config["provider_settings"].update(identifier=True, group_name_display=True, streaming_response=False)
    admins = config.setdefault("admins_id", [])
    if owner not in admins:
        admins.append(owner)
    config["timezone"] = "Asia/Kuala_Lumpur"

    directory = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", dir=directory, delete=False) as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        temporary = file.name
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    print("configured", path)


if __name__ == "__main__":
    main(sys.argv[1])
