"""Gemini adapter (google-genai SDK, stateless `generate_content`).

Model turns are appended to the history exactly as returned, because Gemini 3
models attach thought signatures to parts and require them back unchanged in
multi-turn function calling.
"""

import time
import uuid

from google import genai
from google.genai import errors, types

from app.llm.base import (
    Conversation,
    LLMError,
    LLMResponse,
    RateLimited,
    ToolCall,
    ToolResult,
    ToolSpec,
    TransientLLMError,
)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, timeout_s: float = 90.0) -> None:
        self._client = genai.Client(
            api_key=api_key,
            # We own retries (and record each attempt as an event), so the SDK must not retry silently.
            http_options=types.HttpOptions(
                timeout=int(timeout_s * 1000), retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    def start(self, system: str, user: str) -> Conversation:
        return Conversation(
            system=system, messages=[types.UserContent(parts=[types.Part.from_text(text=user)])]
        )

    async def generate(self, conv: Conversation, model: str, tools: list[ToolSpec]) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=conv.system,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name, description=t.description, parameters_json_schema=t.parameters
                        )
                        for t in tools
                    ]
                )
            ],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=types.FunctionCallingConfigMode.ANY)
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )
        start = time.perf_counter()
        try:
            resp = await self._client.aio.models.generate_content(
                model=model, contents=conv.messages, config=config
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise RateLimited(f"Gemini rate limit: {exc.message}") from exc
            if exc.code >= 500 or exc.code == 408:
                raise TransientLLMError(f"Gemini {exc.code}: {exc.message}") from exc
            raise LLMError(f"Gemini {exc.code}: {exc.message}") from exc
        except (TimeoutError, OSError) as exc:
            raise TransientLLMError(f"Gemini request failed: {exc}") from exc
        latency_ms = int((time.perf_counter() - start) * 1000)

        candidate = resp.candidates[0] if resp.candidates else None
        if candidate is None or candidate.content is None:
            reason = resp.prompt_feedback.block_reason if resp.prompt_feedback else None
            raise LLMError(f"Gemini returned no content (block_reason={reason})")
        conv.messages.append(candidate.content)

        calls = [
            ToolCall(
                id=fc.id or f"call_{uuid.uuid4().hex[:12]}", name=fc.name or "", arguments=dict(fc.args or {})
            )
            for fc in (resp.function_calls or [])
        ]
        usage = resp.usage_metadata
        # Visible text only; thought parts are internal reasoning and are not shown as narration.
        text = "".join(p.text for p in (candidate.content.parts or []) if p.text and not p.thought)
        return LLMResponse(
            model=model,
            text=text,
            tool_calls=calls,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            # Output prices include thinking tokens, so they count toward the budget too.
            output_tokens=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
            if usage
            else 0,
            finish_reason=str(candidate.finish_reason.value) if candidate.finish_reason else None,
            latency_ms=latency_ms,
        )

    def add_user_message(self, conv: Conversation, text: str) -> None:
        conv.messages.append(types.UserContent(parts=[types.Part.from_text(text=text)]))

    def add_tool_results(self, conv: Conversation, results: list[ToolResult]) -> None:
        parts = []
        for r in results:
            part = types.Part.from_function_response(name=r.call.name, response=r.content)
            if part.function_response is not None:
                part.function_response.id = r.call.id
            parts.append(part)
        conv.messages.append(types.Content(role="user", parts=parts))
