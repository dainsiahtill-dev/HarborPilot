"""Streaming tag parser for real-time <thinking> and <answer> tag parsing

This module provides a StreamingTagParser class that handles token-level
tag detection and parsing for streaming output, enabling structured
real-time display of thinking and answer content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TagState(Enum):
    IDLE = "idle"
    IN_THINKING = "in_thinking"
    IN_ANSWER = "in_answer"
    IN_FINAL = "in_final"


THINKING_TAGS = ["thinking", "reasoning", "analysis", "think"]
ANSWER_TAGS = ["answer", "final", "response"]


@dataclass
class TagEvent:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data}


class StreamingTagParser:
    def __init__(self, flush_threshold: int = 20):
        self.flush_threshold = flush_threshold
        self.buffer = ""
        self.current_state = TagState.IDLE
        self.content_buffer = ""
        self.is_tag_mode = False
        self._tag_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        return {
            "thinking_open": re.compile(
                rf"<({'|'.join(THINKING_TAGS)})[^>]*>", re.IGNORECASE
            ),
            "thinking_close": re.compile(
                rf"</({'|'.join(THINKING_TAGS)})>", re.IGNORECASE
            ),
            "answer_open": re.compile(
                rf"<({'|'.join(ANSWER_TAGS)})[^>]*>", re.IGNORECASE
            ),
            "answer_close": re.compile(
                rf"</({'|'.join(ANSWER_TAGS)})>", re.IGNORECASE
            ),
        }

    def detect_tag_mode(self, text: str) -> bool:
        if not text:
            return False
        thinking_match = self._tag_patterns["thinking_open"].search(text)
        answer_match = self._tag_patterns["answer_open"].search(text)
        return bool(thinking_match or answer_match)

    def process_chunk(self, chunk: str) -> List[TagEvent]:
        events: List[TagEvent] = []
        self.buffer += chunk

        while self.buffer:
            if self.current_state == TagState.IDLE:
                events.extend(self._handle_idle_state())
            elif self.current_state == TagState.IN_THINKING:
                events.extend(self._handle_thinking_state())
            elif self.current_state == TagState.IN_ANSWER:
                events.extend(self._handle_answer_state())
            elif self.current_state == TagState.IN_FINAL:
                events.extend(self._handle_final_state())

            if not events:
                break

        return events

    def _handle_idle_state(self) -> List[TagEvent]:
        events: List[TagEvent] = []
        timestamp = self._utc_now()

        thinking_open = self._tag_patterns["thinking_open"].search(self.buffer)
        answer_open = self._tag_patterns["answer_open"].search(self.buffer)

        if thinking_open and (
            not answer_open or thinking_open.start() < answer_open.start()
        ):
            self.current_state = TagState.IN_THINKING
            self.buffer = self.buffer[: thinking_open.start()] + self.buffer[
                thinking_open.end() :
            ]
            events.append(
                TagEvent(type="thinking_start", data={"timestamp": timestamp})
            )
        elif answer_open:
            self.current_state = TagState.IN_ANSWER
            self.buffer = self.buffer[: answer_open.start()] + self.buffer[
                answer_open.end() :
            ]
            events.append(
                TagEvent(type="answer_start", data={"timestamp": timestamp})
            )
        else:
            return events

        return events

    def _handle_thinking_state(self) -> List[TagEvent]:
        events: List[TagEvent] = []
        timestamp = self._utc_now()

        thinking_close = self._tag_patterns["thinking_close"].search(self.buffer)

        if thinking_close:
            content = self.buffer[: thinking_close.start()]
            self.buffer = self.buffer[thinking_close.end() :]

            if content:
                events.append(
                    TagEvent(
                        type="thinking_chunk",
                        data={"content": content, "is_complete": True},
                    )
                )

            events.append(
                TagEvent(type="thinking_end", data={"timestamp": timestamp})
            )
            self._reset_thinking_state()
        else:
            if len(self.buffer) >= self.flush_threshold:
                content = self.buffer
                self.buffer = ""
                events.append(
                    TagEvent(
                        type="thinking_chunk",
                        data={"content": content, "is_complete": False},
                    )
                )

        return events

    def _handle_answer_state(self) -> List[TagEvent]:
        events: List[TagEvent] = []
        timestamp = self._utc_now()

        answer_close = self._tag_patterns["answer_close"].search(self.buffer)

        if answer_close:
            content = self.buffer[: answer_close.start()]
            self.buffer = self.buffer[answer_close.end() :]

            if content:
                events.append(
                    TagEvent(
                        type="answer_chunk",
                        data={"content": content, "is_complete": True},
                    )
                )

            events.append(
                TagEvent(type="answer_end", data={"timestamp": timestamp})
            )
            self._reset_answer_state()
        else:
            if len(self.buffer) >= self.flush_threshold:
                content = self.buffer
                self.buffer = ""
                events.append(
                    TagEvent(
                        type="answer_chunk",
                        data={"content": content, "is_complete": False},
                    )
                )

        return events

    def _handle_final_state(self) -> List[TagEvent]:
        events: List[TagEvent] = []
        timestamp = self._utc_now()

        final_close = self._tag_patterns["answer_close"].search(self.buffer)

        if final_close:
            content = self.buffer[: final_close.start()]
            self.buffer = self.buffer[final_close.end() :]

            if content:
                events.append(
                    TagEvent(
                        type="answer_chunk",
                        data={"content": content, "is_complete": True},
                    )
                )

            events.append(
                TagEvent(type="answer_end", data={"timestamp": timestamp})
            )
            self._reset_answer_state()
        else:
            if len(self.buffer) >= self.flush_threshold:
                content = self.buffer
                self.buffer = ""
                events.append(
                    TagEvent(
                        type="answer_chunk",
                        data={"content": content, "is_complete": False},
                    )
                )

        return events

    def _reset_thinking_state(self) -> None:
        self.content_buffer = ""
        self._transition_to_idle_if_safe()

    def _reset_answer_state(self) -> None:
        self.content_buffer = ""
        self._transition_to_idle_if_safe()

    def _transition_to_idle_if_safe(self) -> None:
        if self.current_state in (TagState.IN_THINKING, TagState.IN_ANSWER):
            open_tags = self._count_open_tags()
            if open_tags == 0:
                self.current_state = TagState.IDLE

    def _count_open_tags(self) -> int:
        thinking_open = len(self._tag_patterns["thinking_open"].findall(self.buffer))
        answer_open = len(self._tag_patterns["answer_open"].findall(self.buffer))
        thinking_close = len(self._tag_patterns["thinking_close"].findall(self.buffer))
        answer_close = len(self._tag_patterns["answer_close"].findall(self.buffer))
        return (thinking_open + answer_open) - (thinking_close + answer_close)

    def flush(self) -> List[TagEvent]:
        events: List[TagEvent] = []

        if self.current_state == TagState.IN_THINKING and self.buffer:
            events.append(
                TagEvent(
                    type="thinking_chunk",
                    data={"content": self.buffer, "is_complete": False},
                )
            )
            events.append(
                TagEvent(type="thinking_end", data={"timestamp": self._utc_now()})
            )
        elif self.current_state == TagState.IN_ANSWER and self.buffer:
            events.append(
                TagEvent(
                    type="answer_chunk",
                    data={"content": self.buffer, "is_complete": False},
                )
            )
            events.append(
                TagEvent(type="answer_end", data={"timestamp": self._utc_now()})
            )

        self.reset()
        return events

    def reset(self) -> None:
        self.buffer = ""
        self.current_state = TagState.IDLE
        self.content_buffer = ""
        self.is_tag_mode = False

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()


def create_tag_parser(flush_threshold: int = 20) -> StreamingTagParser:
    return StreamingTagParser(flush_threshold=flush_threshold)
