"""Claude-Ojouchan core: raw message ledger, daily spend cap and a temporary persona."""

import os
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.provider.sources.anthropic_source import ProviderAnthropic

from .ledger import Ledger
from .spend import Spend

DATA = Path("data/ojou")
TIMEZONE = "Asia/Kuala_Lumpur"
SOURCE_URL = "https://github.com/yohaneowo/claude-ojouchan"

# Placeholder until the persona is designed. It is the same text on every call, so it stays cached.
PERSONA = """你是 Ojouchan（お嬢ちゃん），在 Discord 伺服器裡和大家聊天的女孩子。人設還沒定案，現在先：
- 像群友一樣自然地聊天，回覆簡短，一兩句為主。
- 用對方使用的語言回覆。
- 不知道就說不知道，不要編造。"""


def install_spend_hooks(spend: Spend) -> None:
    """Wrap AstrBot's Anthropic provider: refuse calls past the daily cap and record every response.

    `_extract_usage` receives the raw usage of each non-streaming response (cache writes included),
    so tool loops are counted call by call. Streaming responses are not counted; keep streaming off.
    """
    if getattr(ProviderAnthropic, "_ojou_original", None) is None:
        ProviderAnthropic._ojou_original = (ProviderAnthropic._query, ProviderAnthropic._extract_usage)
    query, extract_usage = ProviderAnthropic._ojou_original

    async def _query(provider, payloads, tools, **kwargs):
        spend.check()
        return await query(provider, payloads, tools, **kwargs)

    def _extract_usage(provider, usage):
        if usage is not None:
            try:
                spend.record(provider.get_model(), usage)
            except Exception:
                logger.exception("ojou: failed to record usage")
        return extract_usage(provider, usage)

    ProviderAnthropic._query = _query
    ProviderAnthropic._extract_usage = _extract_usage


def remove_spend_hooks() -> None:
    original = getattr(ProviderAnthropic, "_ojou_original", None)
    if original:
        ProviderAnthropic._query, ProviderAnthropic._extract_usage = original
        ProviderAnthropic._ojou_original = None


@register("astrbot_plugin_ojou_core", "yohaneowo", "Claude-Ojouchan core", "0.1.0")
class OjouCore(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.owner = os.environ.get("OJOU_OWNER_ID", "")
        cap = float(os.environ.get("OJOU_DAILY_BUDGET_USD", "2"))
        self.spend = Spend(DATA / "usage", cap, TIMEZONE)
        self.ledger = Ledger(DATA / "archive", TIMEZONE)
        self.owner_dm = DATA / "owner-dm.txt"
        # (day, session) pairs already told that today's budget is used up.
        self.notified: set[tuple[str, str]] = set()
        install_spend_hooks(self.spend)
        if self.context.get_config().get("provider_settings", {}).get("streaming_response"):
            logger.warning("ojou: streaming is on, so spend is undercounted")

    async def terminate(self):
        remove_spend_hooks()

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def record_incoming(self, event: AstrMessageEvent):
        message = event.message_obj
        self.ledger.write(
            {
                "dir": "in",
                "session": event.unified_msg_origin,
                "id": str(getattr(message, "message_id", "") or ""),
                "group": event.get_group_id() or None,
                "user": event.get_sender_id(),
                "name": event.get_sender_name(),
                "text": event.get_message_outline(),
            }
        )
        # Remember where the owner's DMs are, so budget alerts can reach them.
        if self.owner and event.get_sender_id() == self.owner and event.is_private_chat():
            self.owner_dm.write_text(event.unified_msg_origin, encoding="utf-8")

    @filter.after_message_sent()
    async def record_outgoing(self, event: AstrMessageEvent):
        result = event.get_result()
        text = result.get_plain_text() if result else ""
        if text:
            self.ledger.write(
                {
                    "dir": "out",
                    "session": event.unified_msg_origin,
                    "group": event.get_group_id() or None,
                    "text": text,
                }
            )

    @filter.on_llm_request()
    async def before_llm(self, event: AstrMessageEvent, req: ProviderRequest):
        if self.spend.over():
            event.stop_event()
            await self.announce_cap(event)
            return
        req.system_prompt = f"{req.system_prompt or ''}\n# Ojouchan\n{PERSONA}\n"

    async def announce_cap(self, event: AstrMessageEvent) -> None:
        day = self.spend.today()
        session = event.unified_msg_origin
        if (day, session) not in self.notified:
            self.notified.add((day, session))
            await event.send(MessageChain().message("今天的額度用完了，明天再陪你聊～"))
        if (day, "owner") not in self.notified and self.owner_dm.exists():
            self.notified.add((day, "owner"))
            text = f"今天的 Claude 花費到 ${self.spend.spent():.2f}（上限 ${self.spend.cap:.2f}），之後的訊息先不回。"
            await self.context.send_message(self.owner_dm.read_text(encoding="utf-8"), MessageChain().message(text))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("spend")
    async def spend_command(self, event: AstrMessageEvent):
        """今天的 Claude 花費"""
        yield event.plain_result(f"今天已用 ${self.spend.spent():.4f}，上限 ${self.spend.cap:.2f}")

    @filter.command("source")
    async def source_command(self, event: AstrMessageEvent):
        """原始碼位置"""
        yield event.plain_result(f"我的原始碼（AGPL-3.0）：{SOURCE_URL}")
