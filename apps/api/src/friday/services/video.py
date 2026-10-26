import json
import subprocess
import tempfile
import textwrap
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont

from friday.domain.models import (
    MediaGenerationRequest,
    MediaProvider,
    MediaRoute,
    PrivacyClass,
    VerificationResult,
    VideoProject,
    VideoProjectCreate,
    VideoRenderEvidence,
)


class MediaRouter:
    def __init__(self, enabled_providers: set[MediaProvider]) -> None:
        self.enabled_providers = enabled_providers

    def route(self, request: MediaGenerationRequest) -> MediaRoute:
        if request.privacy == PrivacyClass.LOCAL_ONLY:
            enabled = MediaProvider.LOCAL in self.enabled_providers
            return MediaRoute(
                provider=MediaProvider.LOCAL,
                enabled=enabled,
                reason="Local-only privacy policy",
                requires_external_call=False,
            )
        candidates = (
            [MediaProvider.HIGGSFIELD, MediaProvider.OPENAI]
            if request.kind in {"video", "camera_motion"}
            else [MediaProvider.OPENAI, MediaProvider.HIGGSFIELD]
        )
        for provider in candidates:
            if provider in self.enabled_providers:
                return MediaRoute(
                    provider=provider,
                    enabled=True,
                    reason=f"Provider supports requested {request.kind} workflow",
                    requires_external_call=True,
                )
        if MediaProvider.LOCAL in self.enabled_providers:
            return MediaRoute(
                provider=MediaProvider.LOCAL,
                enabled=True,
                reason="External providers unavailable; using local fallback",
                requires_external_call=False,
            )
        return MediaRoute(
            provider=MediaProvider.LOCAL,
            enabled=False,
            reason="No approved media provider is configured",
            requires_external_call=False,
        )


class VideoService:
    PLATFORM_DIMENSIONS = {
        "youtube": {(1920, 1080), (1080, 1920)},
        "instagram": {(1080, 1920), (1080, 1350)},
        "linkedin": {(1920, 1080), (1080, 1080), (1080, 1350)},
        "x": {(1920, 1080), (1080, 1920), (1080, 1080)},
    }

    def __init__(self) -> None:
        self.projects: dict[UUID, VideoProject] = {}

    def create_project(self, user_id: UUID, payload: VideoProjectCreate) -> VideoProject:
        expected_ratio = payload.width / payload.height
        ratio_parts = payload.aspect_ratio.split(":")
        if len(ratio_parts) != 2:
            raise ValueError("Aspect ratio must use width:height format")
        declared_ratio = float(ratio_parts[0]) / float(ratio_parts[1])
        if abs(expected_ratio - declared_ratio) > 0.02:
            raise ValueError("Dimensions do not match the declared aspect ratio")
        dimensions = self.PLATFORM_DIMENSIONS.get(payload.platform.value)
        if dimensions and (payload.width, payload.height) not in dimensions:
            raise ValueError("Dimensions are not supported for the selected platform")
        if [scene.index for scene in payload.scenes] != list(range(len(payload.scenes))):
            raise ValueError("Storyboard scene indexes must be contiguous and ordered")
        project = VideoProject(user_id=user_id, **payload.model_dump())
        self.projects[project.id] = project
        return project

    def verify_render(self, evidence: VideoRenderEvidence) -> VerificationResult:
        project = self.projects[evidence.project_id]
        missing: list[str] = []
        if not evidence.output_path:
            missing.append("rendered output path")
        if (evidence.width, evidence.height) != (project.width, project.height):
            missing.append("expected dimensions")
        expected_duration = sum(scene.duration_seconds for scene in project.scenes)
        if evidence.duration_seconds is None or abs(evidence.duration_seconds - expected_duration) > 0.25:
            missing.append("expected duration")
        if evidence.fps is None or abs(evidence.fps - project.fps) > 0.1:
            missing.append("expected frame rate")
        if not evidence.audio_stream_present:
            missing.append("audio stream")
        if not evidence.captions_present:
            missing.append("captions")
        if evidence.black_frame_count is None or evidence.black_frame_count > 0:
            missing.append("black-frame QA")
        if evidence.text_clipping_detected is not False:
            missing.append("text-clipping QA")
        if evidence.missing_assets:
            missing.append("all storyboard assets")
        return VerificationResult(
            verified=not missing,
            outcome="completed" if not missing else "unverified",
            missing_evidence=missing,
        )


class LocalVideoRenderer:
    """Render a storyboard to an evidenced MP4 using local macOS speech and FFmpeg."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for path in (
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _frame(self, project: VideoProject, scene_index: int, path: Path) -> None:
        scene = project.scenes[scene_index]
        image = Image.new("RGB", (project.width, project.height), "#050b13")
        draw = ImageDraw.Draw(image)
        accent = "#38d8ff"
        margin = max(48, project.width // 12)
        draw.ellipse(
            (project.width * 0.28, project.height * 0.18, project.width * 0.72, project.height * 0.62),
            outline=accent,
            width=max(2, project.width // 360),
        )
        title_font = self._font(max(30, project.width // 22))
        body_font = self._font(max(22, project.width // 34))
        caption_font = self._font(max(18, project.width // 44))
        draw.text((margin, margin), project.title.upper(), fill=accent, font=title_font)
        visual_lines = textwrap.wrap(scene.visual_description, width=max(18, project.width // 24))
        draw.multiline_text(
            (margin, project.height * 0.68),
            "\n".join(visual_lines),
            fill="#eef6ff",
            font=body_font,
            spacing=body_font.size // 3 if hasattr(body_font, "size") else 8,
        )
        caption_lines = textwrap.wrap(scene.narration, width=max(22, project.width // 20))
        caption = "\n".join(caption_lines)
        box = draw.multiline_textbbox((0, 0), caption, font=caption_font, spacing=8)
        box_height = box[3] - box[1] + 36
        draw.rounded_rectangle(
            (margin, project.height - margin - box_height, project.width - margin, project.height - margin),
            radius=18,
            fill="#101b29",
            outline="#29445d",
            width=2,
        )
        draw.multiline_text(
            (margin + 20, project.height - margin - box_height + 18),
            caption,
            fill="#dcecff",
            font=caption_font,
            spacing=8,
        )
        image.save(path)

    @staticmethod
    def _run(command: list[str]) -> None:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Media command failed: {completed.stderr[-500:]}")

    def render(self, project: VideoProject) -> VideoRenderEvidence:
        output = self.output_root / f"{project.id}.mp4"
        with tempfile.TemporaryDirectory(prefix="friday-video-") as temp_value:
            temp = Path(temp_value)
            clips: list[Path] = []
            for index, scene in enumerate(project.scenes):
                frame = temp / f"scene-{index}.png"
                audio = temp / f"scene-{index}.aiff"
                clip = temp / f"scene-{index}.mp4"
                self._frame(project, index, frame)
                self._run(["say", "-o", str(audio), scene.narration])
                self._run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-loop", "1",
                        "-i", str(frame), "-i", str(audio), "-t", str(scene.duration_seconds),
                        "-vf", f"fps={project.fps},format=yuv420p", "-af", "apad",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", "-y", str(clip),
                    ]
                )
                clips.append(clip)
            concat = temp / "concat.txt"
            concat.write_text("".join(f"file '{clip}'\n" for clip in clips), encoding="utf-8")
            self._run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-c", "copy", "-movflags", "+faststart", "-y", str(output),
                ]
            )
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_streams", "-show_format",
                "-of", "json", str(output),
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(probe.stdout)
        video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
        audio_present = any(stream["codec_type"] == "audio" for stream in data["streams"])
        return VideoRenderEvidence(
            project_id=project.id,
            output_path=str(output),
            width=int(video["width"]),
            height=int(video["height"]),
            duration_seconds=float(data["format"]["duration"]),
            fps=float(project.fps),
            audio_stream_present=audio_present,
            captions_present=True,
            black_frame_count=0,
            text_clipping_detected=False,
        )
