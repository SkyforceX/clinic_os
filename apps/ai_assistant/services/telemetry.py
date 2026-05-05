from __future__ import annotations

import json
import logging
from datetime import datetime


logger = logging.getLogger("apps.ai_assistant.telemetry")

EVENT_PREFIX = "AI_TOOL_EVENT "


def emit_ai_tool_event(event_type: str, **payload) -> None:
    event = {
        "event_type": event_type,
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    for key, value in payload.items():
        if value is None:
            continue
        event[key] = value
    logger.info("%s%s", EVENT_PREFIX, json.dumps(event, ensure_ascii=False, sort_keys=True))
