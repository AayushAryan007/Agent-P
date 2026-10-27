# ADR-0002: Gemini free tier as the first LLM provider, Groq as second

- Status: Accepted (model names to be verified in Phase 5)
- Date: 2026-10-27

## Context

The project must run on a free budget, including a public demo. The provider must support function/tool calling and schema-constrained structured output, since agents return typed results.

## Options

| | Gemini API (free tier) | Groq (free tier) |
|---|---|---|
| Tool calling | Native function calling | OpenAI-compatible tool calling; reliability varies by model |
| Structured output | JSON schema response mode | JSON mode / tool-based; model dependent |
| Context | Very large | Smaller, model dependent |
| Latency | Good | Very fast |
| Rate limits | Per-minute/per-day caps on free tier | Per-minute/per-day caps on free tier |
| Data use | Free-tier prompts may be used to improve Google products | See current Groq terms |

Limits and model availability change frequently; exact values must be read from official docs at integration time and recorded in TECH_STACK.md.

## Decision

Start with **Gemini (free tier)** behind an `LLMProvider` interface (`generate(messages, tools, response_schema) -> LLMResult` with usage metadata). Add a **Groq** adapter as the first P1 provider so a rate-limited demo can fall back. Ollama remains possible through the same interface.

## Consequences

- + Zero cost; large context helps repository analysis.
- − Free-tier rate limits constrain concurrency → 1 active run on the demo, per-run budgets, and recorded showcase runs for replay.
- − Only public/demo code may be sent (free-tier data use); enforced by ADR-0003 restricting sources to public repos.
- No model name is hardcoded; the model is configuration, validated at startup against the provider's model list.

## Update 2026-10-27 — models selected

Verified against official docs: default `gemini-3.8-flash`, fallback `gemini-3.5-flash-lite`, Groq P1 `openai/gpt-oss-120b`. Details and sources in [TECH_STACK.md](../TECH_STACK.md#llm-models-verified-2026-10-27-against-official-docs).
