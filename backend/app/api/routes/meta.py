"""Static capabilities: templates, bundled repos, configured providers (never key values)."""

from fastapi import APIRouter

from app.api.deps import Services
from app.api.schemas import (
    BundledRepoOut,
    Limits,
    MetaOut,
    ModelInfo,
    ProviderOut,
    StepDefinitionOut,
    TemplateOut,
    ToolInfoOut,
)
from app.config import Settings
from app.orchestrator.templates import BUNDLED_REPOS, TEMPLATES

router = APIRouter(tags=["meta"])


def providers(settings: Settings) -> list[ProviderOut]:
    return [
        ProviderOut(
            name="gemini",
            configured=settings.gemini_api_key is not None,
            models=[
                ModelInfo(id=settings.gemini_model, role="default"),
                ModelInfo(id=settings.gemini_fallback_model, role="fallback"),
            ],
        ),
        ProviderOut(
            name="groq",
            configured=settings.groq_api_key is not None,
            models=[ModelInfo(id=settings.groq_model, role="available")],
        ),
    ]


def provider_for_model(settings: Settings, model: str) -> str | None:
    """Name of a *configured* provider serving this model, or None."""
    for p in providers(settings):
        if p.configured and any(m.id == model for m in p.models):
            return p.name
    return None


def default_limits(settings: Settings) -> Limits:
    return Limits(
        max_minutes=settings.default_max_minutes,
        max_llm_calls=settings.default_max_llm_calls,
        max_total_tokens=settings.default_max_total_tokens,
        max_tool_calls=settings.default_max_tool_calls,
    )


def max_limits(settings: Settings) -> Limits:
    return Limits(
        max_minutes=settings.max_max_minutes,
        max_llm_calls=settings.max_max_llm_calls,
        max_total_tokens=settings.max_max_total_tokens,
        max_tool_calls=settings.max_max_tool_calls,
    )


@router.get("/meta", response_model=MetaOut)
async def meta(svc: Services) -> MetaOut:
    s = svc.settings
    return MetaOut(
        templates=[
            TemplateOut(
                key=t.key,
                title=t.title,
                description=t.description,
                steps=[
                    StepDefinitionOut(
                        id=st.key,
                        key=st.key,
                        kind=st.kind,
                        role=st.role,
                        title=st.title,
                        depends_on=list(st.depends_on),
                    )
                    for st in t.steps
                ],
                tools=[
                    ToolInfoOut(name=x.name, description=x.description, runs_in=x.runs_in) for x in t.tools
                ],
            )
            for t in TEMPLATES.values()
        ],
        bundled_repos=[
            BundledRepoOut(key=r.key, title=r.title, description=r.description)
            for r in BUNDLED_REPOS.values()
        ],
        providers=providers(s),
        limits_default=default_limits(s),
        limits_max=max_limits(s),
    )
