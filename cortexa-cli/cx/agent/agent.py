"""Claude-powered memory intelligence agent with tool_use streaming."""

from __future__ import annotations

import json
import os
from typing import Any

from cx.adapters.base import MemoryAdapter
from cx.agent.system_prompt import SYSTEM_PROMPT
from cx.agent.tools import TOOLS, ToolExecutor, summarize_input, summarize_result


class CortexaAgent:
    """Manages the agentic conversation loop with tool execution.

    Designed to work with Textual's async model — yields events
    that the app renders progressively.
    """

    def __init__(self, adapter: MemoryAdapter) -> None:
        self.adapter = adapter
        self.messages: list[dict[str, Any]] = []
        self.executor = ToolExecutor(adapter)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    async def send_message(self, user_input: str, on_event=None):
        """Send a user message and process the agent response.

        Args:
            user_input: The user's message text.
            on_event: Async callback for progressive rendering.
                Called with event dicts:
                  {"type": "text", "content": str}
                  {"type": "tool_start", "id": str, "name": str, "input_summary": str}
                  {"type": "tool_end", "id": str, "summary": str, "detail": str}
                  {"type": "error", "content": str}
        """
        self.messages.append({"role": "user", "content": user_input})

        try:
            client = self._get_client()
        except Exception as e:
            if on_event:
                await on_event({"type": "error", "content": f"Failed to initialize API client: {e}"})
            return

        # Agent loop — handle tool calls iteratively
        while True:
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=self.messages,
                )
            except Exception as e:
                if on_event:
                    await on_event({"type": "error", "content": f"API error: {e}"})
                return

            assistant_content = response.content
            self.messages.append({"role": "assistant", "content": assistant_content})

            tool_uses = [b for b in assistant_content if b.type == "tool_use"]
            text_blocks = [b for b in assistant_content if b.type == "text"]

            # Emit text blocks
            for block in text_blocks:
                if block.text.strip() and on_event:
                    await on_event({"type": "text", "content": block.text.strip()})

            if not tool_uses:
                break

            # Execute tool calls
            tool_results = []
            for tool_use in tool_uses:
                input_summary = summarize_input(tool_use.input)

                if on_event:
                    await on_event({
                        "type": "tool_start",
                        "id": tool_use.id,
                        "name": tool_use.name,
                        "input_summary": input_summary,
                    })

                result = self.executor.execute(tool_use.name, tool_use.input)
                result_summary = summarize_result(tool_use.name, result)

                if on_event:
                    await on_event({
                        "type": "tool_end",
                        "id": tool_use.id,
                        "summary": result_summary,
                        "detail": result,
                    })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            self.messages.append({"role": "user", "content": tool_results})

            if response.stop_reason != "tool_use":
                break

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
