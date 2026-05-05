from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_assistant.services.telemetry import EVENT_PREFIX


class Command(BaseCommand):
    help = "Summarize native AI tool-calling telemetry from logs/api.log."

    def add_arguments(self, parser):
        parser.add_argument("--tail", type=int, default=5000, help="Number of recent log lines to scan.")

    def handle(self, *args, **options):
        tail = max(int(options["tail"]), 100)
        log_path = Path(settings.LOG_DIR) / "api.log"
        if not log_path.exists():
            self.stdout.write(self.style.WARNING(f"Log file not found: {log_path}"))
            return

        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()

        recent_lines = lines[-tail:]
        events: list[dict] = []
        for line in recent_lines:
            marker_index = line.find(EVENT_PREFIX)
            if marker_index < 0:
                continue
            payload = line[marker_index + len(EVENT_PREFIX):].strip()
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                continue

        if not events:
            self.stdout.write(self.style.WARNING("No AI tool telemetry events found in the selected log window."))
            return

        event_counts = Counter(event.get("event_type") or "unknown" for event in events)
        model_counts = Counter(event.get("model") or "unknown" for event in events if event.get("model"))
        tool_counts = Counter(event.get("tool_name") or "unknown" for event in events if event.get("tool_name"))
        profile_counts = Counter(event.get("profile") or "unknown" for event in events if event.get("profile"))

        self.stdout.write(self.style.SUCCESS(f"AI toolcall telemetry summary from {log_path}"))
        self.stdout.write(f"Scanned recent lines: {len(recent_lines)}")
        self.stdout.write(f"Matched events: {len(events)}")

        self.stdout.write("\nEvent counts:")
        for key, value in event_counts.most_common():
            self.stdout.write(f"- {key}: {value}")

        if model_counts:
            self.stdout.write("\nModels:")
            for key, value in model_counts.most_common():
                self.stdout.write(f"- {key}: {value}")

        if tool_counts:
            self.stdout.write("\nTools:")
            for key, value in tool_counts.most_common():
                self.stdout.write(f"- {key}: {value}")

        if profile_counts:
            self.stdout.write("\nProfiles:")
            for key, value in profile_counts.most_common():
                self.stdout.write(f"- {key}: {value}")
