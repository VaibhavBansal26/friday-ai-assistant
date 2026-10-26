import pytest

from friday.core.config import Settings
from friday.domain.models import ModelCapability, ModelRouteRequest, PrivacyClass
from friday.services.model_router import ModelRouter, ProviderHealth


def settings() -> Settings:
    return Settings(model_default="configured-text", model_realtime="configured-realtime")


def test_local_only_never_routes_to_cloud():
    result = ModelRouter(settings()).route(
        ModelRouteRequest(task_type="private_notes", privacy=PrivacyClass.LOCAL_ONLY)
    )
    assert result.provider == "local"


def test_audio_uses_configured_realtime_route():
    result = ModelRouter(settings()).route(
        ModelRouteRequest(task_type="voice", capabilities={ModelCapability.AUDIO})
    )
    assert result.model == "configured-realtime"
    assert "transport:realtime" in result.reason_codes


def test_unhealthy_openai_falls_back_locally():
    router = ModelRouter(settings(), ProviderHealth(openai=False, local=True))
    assert router.route(ModelRouteRequest(task_type="summary")).provider == "local"


def test_no_eligible_provider_fails_closed():
    router = ModelRouter(settings(), ProviderHealth(openai=False, local=False))
    with pytest.raises(ValueError, match="No healthy model provider"):
        router.route(ModelRouteRequest(task_type="summary"))

