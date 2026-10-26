from uuid import uuid4

from friday.domain.models import (
    ContentPlatform,
    MediaGenerationRequest,
    MediaProvider,
    PrivacyClass,
    StoryboardScene,
    VideoProjectCreate,
    VideoRenderEvidence,
)
from friday.services.video import MediaRouter, VideoService


def project():
    return VideoProjectCreate(
        title="Reliable Friday",
        platform=ContentPlatform.YOUTUBE,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fps=30,
        scenes=[
            StoryboardScene(
                index=0,
                narration="Verify before acting.",
                visual_description="Friday approval screen",
                duration_seconds=5,
            )
        ],
    )


def test_higgsfield_is_optional_and_selected_only_when_enabled():
    request = MediaGenerationRequest(kind="video", prompt="Camera move")
    disabled = MediaRouter({MediaProvider.OPENAI}).route(request)
    enabled = MediaRouter({MediaProvider.HIGGSFIELD}).route(request)
    assert disabled.provider == MediaProvider.OPENAI
    assert enabled.provider == MediaProvider.HIGGSFIELD


def test_local_only_media_never_routes_external():
    route = MediaRouter({MediaProvider.HIGGSFIELD, MediaProvider.LOCAL}).route(
        MediaGenerationRequest(kind="video", prompt="Private project", privacy=PrivacyClass.LOCAL_ONLY)
    )
    assert route.provider == MediaProvider.LOCAL
    assert not route.requires_external_call


def test_render_is_unverified_without_qa_evidence():
    service = VideoService()
    item = service.create_project(uuid4(), project())
    result = service.verify_render(VideoRenderEvidence(project_id=item.id, output_path="video.mp4"))
    assert not result.verified
    assert "expected dimensions" in result.missing_evidence
    assert "captions" in result.missing_evidence


def test_complete_render_evidence_is_verified():
    service = VideoService()
    item = service.create_project(uuid4(), project())
    result = service.verify_render(
        VideoRenderEvidence(
            project_id=item.id,
            output_path="video.mp4",
            width=1080,
            height=1920,
            duration_seconds=5,
            fps=30,
            audio_stream_present=True,
            captions_present=True,
            black_frame_count=0,
            text_clipping_detected=False,
        )
    )
    assert result.verified
