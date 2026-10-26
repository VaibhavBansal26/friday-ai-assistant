from dataclasses import dataclass

from friday.core.config import Settings
from friday.domain.models import (
    ModelCapability,
    ModelRoute,
    ModelRouteRequest,
    PrivacyClass,
)


@dataclass(frozen=True)
class ProviderHealth:
    openai: bool = True
    local: bool = True


class ModelRouter:
    """Policy-based routing. Model identifiers are supplied by configuration."""

    def __init__(self, settings: Settings, health: ProviderHealth | None = None) -> None:
        self.settings = settings
        self.health = health or ProviderHealth()

    def route(self, request: ModelRouteRequest) -> ModelRoute:
        if request.privacy == PrivacyClass.LOCAL_ONLY:
            if not self.health.local:
                raise ValueError("No healthy local model is available for local-only data")
            return ModelRoute(
                provider="local",
                model="local-policy-default",
                reason_codes=["privacy:local_only"],
                timeout_ms=request.maximum_latency_ms or 60_000,
            )

        if ModelCapability.AUDIO in request.capabilities:
            if not self.health.openai:
                raise ValueError("No healthy realtime provider is available")
            return ModelRoute(
                provider="openai",
                model=self.settings.model_realtime,
                fallback_models=["local-realtime-fallback"] if self.health.local else [],
                reason_codes=["capability:audio", "transport:realtime"],
                timeout_ms=request.maximum_latency_ms or 15_000,
            )

        if self.health.openai:
            reasons = [f"task:{request.task_type}", f"reasoning:{request.reasoning_depth}"]
            if ModelCapability.TOOLS in request.capabilities:
                reasons.append("capability:tools")
            return ModelRoute(
                provider="openai",
                model=self.settings.model_default,
                fallback_models=["local-policy-default"] if self.health.local else [],
                reason_codes=reasons,
                timeout_ms=request.maximum_latency_ms or 45_000,
            )

        if self.health.local:
            return ModelRoute(
                provider="local",
                model="local-policy-default",
                reason_codes=["fallback:provider_unhealthy"],
                timeout_ms=request.maximum_latency_ms or 60_000,
            )
        raise ValueError("No healthy model provider satisfies this request")

