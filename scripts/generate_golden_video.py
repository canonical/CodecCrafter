#!/usr/bin/env python3
"""
Generate reproducible golden video samples with configurable parameters.

Supports multiple codecs (H.264, H.265, VP8, VP9, AV1, MPEG-4) with maximum
reproducibility settings for consistent, bit-exact output across different
machines and runs.
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

# Resolution presets (keyed lowercase; looked up case-insensitively)
RESOLUTION_PRESETS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2160p": (3840, 2160),
    "uhd": (3840, 2160),
    "4k": (4096, 2160),
    "8k": (7680, 4320),
}

# Default bitrate: width * height * fps * bits_per_pixel
DEFAULT_BITS_PER_PIXEL = 0.1


class CodecConfig(BaseModel):
    """One codec entry from codecs.yaml."""

    model_config = ConfigDict(extra="forbid")

    encoder: str
    container: str
    speed_type: Literal["preset", "cpu_used", "none"] = "none"
    sc_threshold: bool = False
    keyint_min: bool = True
    extra_essential: List[str] = []
    codec_params: List[str] = []
    aliases: List[str] = []


def _load_codecs() -> Dict[str, CodecConfig]:
    """Load codecs.yaml into a name/alias -> CodecConfig map."""
    config_path = Path(__file__).parent / "config" / "codecs.yaml"
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("codecs.yaml must be a dict mapping names to configs")
    codecs = {
        name.lower(): CodecConfig.model_validate(cfg)
        for name, cfg in raw.items()
    }
    for name, cfg in list(codecs.items()):
        for alias in cfg.aliases:
            codecs[alias.lower()] = cfg
    return codecs


CODECS: Dict[str, CodecConfig] = _load_codecs()


def encoder_available(encoder: str) -> bool:
    """Check that FFmpeg ships the given encoder."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return encoder in result.stdout


class BaseVideoConfig(BaseModel):
    """Configuration for a single video generation task (shared fields)."""

    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)
    codec: str
    duration: float = Field(gt=0)
    bitrate: Optional[str] = None
    bits_per_pixel: Optional[float] = Field(default=None, gt=0)
    pix_fmt: str = "yuv420p"
    output_dir: Path = Path(".")
    output_filename: Optional[str] = None
    skip_existing: bool = True
    preset: str = "veryslow"
    extra_params: List[str] = []

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        if v.lower() not in CODECS:
            raise ValueError(f"Unsupported codec: {v}")
        return v

    @property
    def codec_config(self) -> CodecConfig:
        return CODECS[self.codec.lower()]

    def get_filename_suffix(self) -> str:
        """Return filename suffix (override in subclasses, e.g. '_avsync')."""
        return ""

    def get_output_path(self) -> Path:
        """Get the full output path for the video."""
        if self.output_filename:
            filename = self.output_filename
        else:
            ext = self.codec_config.container
            suffix = self.get_filename_suffix()
            filename = (
                f"{self.height}p_{self.fps}fps_{self.codec}{suffix}.{ext}"
            )
        return self.output_dir / filename

    def get_bitrate(
        self, global_bits_per_pixel: Optional[float] = None
    ) -> str:
        """Explicit bitrate, or width * height * fps * bits_per_pixel."""
        if self.bitrate:
            return self.bitrate
        bpp = (
            self.bits_per_pixel
            or global_bits_per_pixel
            or DEFAULT_BITS_PER_PIXEL
        )
        bits = self.width * self.height * self.fps * bpp
        if bits >= 1_000_000:
            return f"{int(bits / 1_000_000)}M"
        if bits >= 1_000:
            return f"{int(bits / 1_000)}k"
        return str(int(bits))

    def _build_encoding_args(
        self, global_bits_per_pixel: Optional[float] = None
    ) -> List[str]:
        """Return common encoding args for video."""
        cfg = self.codec_config
        gop_size = self.fps * 2
        args = [
            "-c:v",
            cfg.encoder,
            "-pix_fmt",
            self.pix_fmt,
            "-b:v",
            self.get_bitrate(global_bits_per_pixel),
        ]
        if cfg.speed_type == "preset":
            args += ["-preset", self.preset]
        elif cfg.speed_type == "cpu_used":
            args += ["-cpu-used", "0"]
        args += ["-threads", "1", "-g", str(gop_size)]
        if cfg.keyint_min:
            args += ["-keyint_min", str(gop_size)]
        if cfg.sc_threshold:
            args += ["-sc_threshold", "0"]
        return args + cfg.extra_essential + cfg.codec_params

    def build_ffmpeg_command(
        self, global_bits_per_pixel: Optional[float] = None
    ) -> List[str]:
        """Build FFmpeg command for this config. Subclasses must override."""
        raise NotImplementedError


class TestPatternVideoConfig(BaseVideoConfig):
    """Configuration for golden videos using lavfi test sources (testsrc2)."""

    test_pattern: str = "testsrc2"

    def build_ffmpeg_command(
        self, global_bits_per_pixel: Optional[float] = None
    ) -> List[str]:
        """Build FFmpeg command for test pattern scenario."""
        source = (
            f"{self.test_pattern}=size={self.width}x{self.height}:"
            f"rate={self.fps}:duration={self.duration}"
        )
        return (
            ["ffmpeg", "-bitexact", "-fflags", "+bitexact"]
            + ["-f", "lavfi", "-i", source]
            + self._build_encoding_args(global_bits_per_pixel)
            + ["-map_metadata", "-1"]
            + self.extra_params
            + [str(self.get_output_path())]
        )


class AvSyncVideoConfig(BaseVideoConfig):
    """Configuration for AV sync test videos (beep every second)."""

    duration: float = Field(
        ge=0.1, description="AV sync requires duration >= 0.1 seconds"
    )
    audio_frequency: int = 1000
    beep_duration: float = 0.1

    def get_filename_suffix(self) -> str:
        """Return '_avsync' suffix for AV sync output filenames."""
        return "_avsync"

    def _build_filter_complex(self) -> str:
        """Build filter_complex string for AV sync (beep every second)."""
        beep_dur = self.beep_duration
        num_beeps = max(1, int(self.duration))

        enable_expr = f"lt(mod(t\\,1),{beep_dur})"
        video_filters = [
            f"[0:v]drawbox=0:0:{self.width}:{self.height}:white:t=fill:"
            f"enable='{enable_expr}'[v]"
        ]

        beep_filters = []
        beep_labels = []
        for i in range(num_beeps):
            delay_ms = i * 1000
            label = f"beep{i}"
            beep_filters.append(
                f"[2:a]aloop=loop=-1:size=2e+09,atrim=0:{beep_dur},"
                f"asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms}[{label}]"
            )
            beep_labels.append(f"[{label}]")

        amix_inputs = "[1:a]" + "".join(beep_labels)
        n = num_beeps + 1
        amix_filter = f"{amix_inputs}amix=inputs={n}:duration=first[a]"

        return "; ".join(video_filters + beep_filters + [amix_filter])

    def build_ffmpeg_command(
        self, global_bits_per_pixel: Optional[float] = None
    ) -> List[str]:
        """Build FFmpeg command for AV sync scenario."""
        color_src = (
            f"color=c=black:s={self.width}x{self.height}:"
            f"d={self.duration}:r={self.fps}"
        )
        silence_src = f"aevalsrc=0:d={self.duration}:s=48000"
        sine_src = (
            f"sine=frequency={self.audio_frequency}:"
            f"duration={self.beep_duration}"
        )
        audio_codec = (
            "aac" if self.codec_config.container == "mp4" else "libopus"
        )
        return (
            ["ffmpeg"]
            + ["-f", "lavfi", "-i", color_src]
            + ["-f", "lavfi", "-i", silence_src]
            + ["-f", "lavfi", "-i", sine_src]
            + ["-filter_complex", self._build_filter_complex()]
            + ["-map", "[v]", "-map", "[a]"]
            + self._build_encoding_args(global_bits_per_pixel)
            + ["-c:a", audio_codec, "-b:a", "128k"]
            + ["-t", str(self.duration)]
            + [str(self.get_output_path())]
        )


SCENARIOS: Dict[str, type] = {
    "test_pattern": TestPatternVideoConfig,
    "av_sync": AvSyncVideoConfig,
}


class BatchConfig(BaseModel):
    """Schema of a batch config file (JSON or YAML)."""

    model_config = ConfigDict(extra="forbid")

    videos: List[Dict[str, Any]] = Field(min_length=1)
    defaults: Dict[str, Any] = {}
    bits_per_pixel: Optional[float] = Field(default=None, gt=0)


def load_batch_config(config_path: Path) -> BatchConfig:
    """Load and validate a batch config file (YAML superset covers JSON)."""
    return BatchConfig.model_validate(yaml.safe_load(config_path.read_text()))


def parse_resolution(resolution: str) -> Tuple[int, int]:
    """Parse a resolution preset ('1080p', '4K') or '1920x1080' string."""
    preset = RESOLUTION_PRESETS.get(resolution.lower())
    if preset:
        return preset
    match = re.match(r"^(\d+)[x:](\d+)$", resolution)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    raise ValueError(f"Invalid resolution format: {resolution}")


def build_video_config(video: Dict[str, Any]) -> BaseVideoConfig:
    """Build a validated video config from a merged dict.

    Resolves 'scenario' to the config class and 'resolution' to
    width/height; everything else is validated by the model
    (extra='forbid' rejects unknown and cross-scenario keys).
    """
    video = dict(video)
    scenario = video.pop("scenario", "test_pattern")
    if scenario not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario}. "
            f"Must be one of: {sorted(SCENARIOS)}"
        )
    if "resolution" in video:
        resolution = video.pop("resolution")
        if not ("width" in video and "height" in video):
            video["width"], video["height"] = parse_resolution(resolution)
    return SCENARIOS[scenario].model_validate(video)


def merge_batch_video(
    config: BatchConfig, video: Dict[str, Any], cli_output_dir: str
) -> Dict[str, Any]:
    """Merge one batch entry: video > CLI --output-dir > defaults."""
    return {**config.defaults, "output_dir": cli_output_dir, **video}


def format_time(seconds: float) -> str:
    """Format time in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {seconds % 60:.1f}s"


def generate_video(
    config: BaseVideoConfig,
    global_bits_per_pixel: Optional[float] = None,
) -> bool:
    """Generate a single video."""
    output_path = config.get_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if config.skip_existing and output_path.exists():
        print(f"Skipping {output_path.name} (already exists)")
        return False

    encoder = config.codec_config.encoder
    if not encoder_available(encoder):
        print(f"ERROR: Codec encoder '{encoder}' is not available in FFmpeg")
        return False

    cmd = config.build_ffmpeg_command(global_bits_per_pixel)
    print(f"Generating {output_path.name}...")
    print(f"Command: {' '.join(cmd)}")

    start_time = time.time()
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        elapsed = time.time() - start_time
        print(f"✓ Generated {output_path.name} in {format_time(elapsed)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to generate {output_path.name}")
        print(f"Error output: {e.stderr}")
        return False


def run_batch(args: argparse.Namespace) -> int:
    """Run batch mode: config-driven only, no CLI overrides."""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    try:
        config = load_batch_config(config_path)
    except (ValidationError, ValueError) as e:
        print(f"ERROR: Config validation failed: {e}")
        return 1

    total = len(config.videos)
    success_count = 0
    for idx, video in enumerate(config.videos, 1):
        try:
            video_config = build_video_config(
                merge_batch_video(config, video, args.output_dir)
            )
        except (ValidationError, ValueError) as e:
            print(f"ERROR: Video {idx}/{total} config invalid: {e}")
            continue

        print(f"\n[{idx}/{total}] Processing video configuration...")
        if generate_video(video_config, config.bits_per_pixel):
            success_count += 1

    print(f"\n✓ Generated {success_count}/{total} videos successfully")
    return 0 if success_count == total else 1


def run_validate(args: argparse.Namespace) -> int:
    """Validate a batch config file without encoding anything."""
    config_path = Path(args.config)
    try:
        config = load_batch_config(config_path)
        for video in config.videos:
            build_video_config(merge_batch_video(config, video, "."))
    except (ValidationError, ValueError, OSError) as e:
        print(f"ERROR: {config_path}: {e}")
        return 1
    print(f"{config_path}: {len(config.videos)} video configs OK")
    return 0


def add_generic_args(parser: argparse.ArgumentParser) -> None:
    """Add generic arguments shared by test_pattern and av_sync subcommands."""
    resolution_group = parser.add_mutually_exclusive_group()
    resolution_group.add_argument(
        "--resolution",
        type=str,
        help="Resolution preset (480p, 720p, 1080p, 2160p, 4K, 8K) "
        "or explicit (1920x1080)",
    )
    resolution_group.add_argument(
        "--width", type=int, help="Video width (use with --height)"
    )
    parser.add_argument(
        "--height", type=int, help="Video height (use with --width)"
    )
    parser.add_argument(
        "--fps", type=int, required=True, help="Frames per second"
    )
    parser.add_argument(
        "--codec",
        type=str,
        required=True,
        help="Video codec (h264, h265, vp8, vp9, av1, mpeg4)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="Duration in seconds",
    )
    parser.add_argument(
        "--bitrate", type=str, help="Bitrate (e.g., '40M', '5000k')"
    )
    parser.add_argument(
        "--pix-fmt",
        type=str,
        default="yuv420p",
        help="Pixel format (default: yuv420p)",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="veryslow",
        help="FFmpeg preset (default: veryslow)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--output-filename",
        type=str,
        help="Output filename (auto-generated if not provided)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Overwrite existing files",
    )


def run_single_video(args: argparse.Namespace) -> int:
    """Run single video generation (test_pattern or av_sync)."""
    video = {
        "scenario": args.command,
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "codec": args.codec,
        "duration": args.duration,
        "bitrate": args.bitrate,
        "pix_fmt": args.pix_fmt,
        "output_dir": args.output_dir,
        "output_filename": args.output_filename,
        "skip_existing": not args.no_skip_existing,
        "preset": args.preset,
    }
    if args.resolution:
        video["resolution"] = args.resolution
        del video["width"], video["height"]
    if args.command == "test_pattern":
        video["test_pattern"] = args.test_pattern
    else:
        video["audio_frequency"] = args.audio_frequency
        video["beep_duration"] = args.beep_duration

    try:
        video_config = build_video_config(video)
    except (ValidationError, ValueError) as e:
        print(f"ERROR: Invalid config: {e}")
        return 1

    return 0 if generate_video(video_config) else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate reproducible golden video samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp_test = subparsers.add_parser(
        "test_pattern",
        help="Generate golden videos with lavfi test sources",
    )
    add_generic_args(sp_test)
    sp_test.add_argument(
        "--test-pattern",
        type=str,
        default="testsrc2",
        help="Test pattern (default: testsrc2)",
    )

    sp_av = subparsers.add_parser(
        "av_sync",
        help="Generate AV sync test videos (beep every second)",
    )
    add_generic_args(sp_av)
    sp_av.add_argument(
        "--audio-frequency",
        type=int,
        default=1000,
        help="Sine beep frequency in Hz (default: 1000)",
    )
    sp_av.add_argument(
        "--beep-duration",
        type=float,
        default=0.1,
        help="Beep duration in seconds (default: 0.1)",
    )

    sp_batch = subparsers.add_parser(
        "batch",
        help="Batch generation from config file (config-driven only)",
    )
    sp_batch.add_argument(
        "--config",
        type=str,
        required=True,
        help="Configuration file (JSON or YAML)",
    )
    sp_batch.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for generated videos",
    )

    sp_validate = subparsers.add_parser(
        "validate",
        help="Validate a batch config file without encoding",
    )
    sp_validate.add_argument(
        "--config",
        type=str,
        required=True,
        help="Configuration file (JSON or YAML)",
    )

    args = parser.parse_args()

    if args.command == "batch":
        sys.exit(run_batch(args))
    if args.command == "validate":
        sys.exit(run_validate(args))

    if not args.resolution and not (args.width and args.height):
        parser.error("--resolution or --width/--height is required")
    sys.exit(run_single_video(args))


if __name__ == "__main__":
    main()
