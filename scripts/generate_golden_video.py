#!/usr/bin/env python3
"""
Generate reproducible golden video samples with configurable parameters.

Supports multiple codecs (H.264, H.265, VP8, VP9, AV1, MPEG-4) with maximum
reproducibility settings for consistent, bit-exact output across different
machines and runs.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


# Resolution presets
RESOLUTION_PRESETS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2160p": (3840, 2160),
    "UHD": (3840, 2160),
    "4K": (4096, 2160),
    "8K": (7680, 4320),
}

# Default bitrate formula
DEFAULT_BITRATE_FORMULA = "width * height * fps * 0.1"


class CodecHandler:
    """Base class for codec handlers."""

    def __init__(self, encoder: str, container: str):
        self.encoder = encoder
        self.container = container

    def get_encoder(self) -> str:
        """Return the FFmpeg encoder name."""
        return self.encoder

    def get_container(self) -> str:
        """Return the container/extension (e.g., 'mp4', 'webm')."""
        return self.container

    def get_speed_param(self, preset: str) -> List[str]:
        """Return speed/preset parameters for the codec."""
        return []

    def get_essential_params(self, gop_size: int) -> List[str]:
        """Return essential reproducibility parameters."""
        return []

    def get_codec_params(self) -> List[str]:
        """Return codec-specific parameters for reproducibility."""
        return []


class H264Handler(CodecHandler):
    """Handler for H.264 codec."""

    def __init__(self):
        super().__init__("libx264", "mp4")

    def get_speed_param(self, preset: str) -> List[str]:
        return ["-preset", preset]

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
            "-sc_threshold",
            "0",
        ]

    def get_codec_params(self) -> List[str]:
        return [
            "-x264-params",
            "deterministic=1:no-mbtree=1:no-mixed-refs=1",
        ]


class H265Handler(CodecHandler):
    """Handler for H.265/HEVC codec."""

    def __init__(self):
        super().__init__("libx265", "mp4")

    def get_speed_param(self, preset: str) -> List[str]:
        return ["-preset", preset]

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
            "-sc_threshold",
            "0",
        ]

    def get_codec_params(self) -> List[str]:
        return [
            "-x265-params",
            "deterministic=1:no-open-gop=1:no-wpp=1:no-pmode=1:no-pme=1",
        ]


class VP8Handler(CodecHandler):
    """Handler for VP8 codec."""

    def __init__(self):
        super().__init__("libvpx", "webm")

    def get_speed_param(self, preset: str) -> List[str]:
        return ["-cpu-used", "0"]

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
        ]


class VP9Handler(CodecHandler):
    """Handler for VP9 codec."""

    def __init__(self):
        super().__init__("libvpx-vp9", "webm")

    def get_speed_param(self, preset: str) -> List[str]:
        return ["-cpu-used", "0"]

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
            "-tile-columns",
            "0",
            "-tile-rows",
            "0",
            "-row-mt",
            "0",
        ]


class AV1Handler(CodecHandler):
    """Handler for AV1 codec."""

    def __init__(self):
        super().__init__("libaom-av1", "webm")

    def get_speed_param(self, preset: str) -> List[str]:
        return ["-cpu-used", "0"]

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
        ]


class MPEG4Handler(CodecHandler):
    """Handler for MPEG-4 codec."""

    def __init__(self):
        super().__init__("mpeg4", "mp4")

    def get_essential_params(self, gop_size: int) -> List[str]:
        return [
            "-threads",
            "1",
            "-g",
            str(gop_size),
        ]


class CodecRegistry:
    """Registry for codec handlers."""

    def __init__(self):
        self._handlers: Dict[str, CodecHandler] = {}
        self._aliases: Dict[str, str] = {}
        self._register_default_codecs()

    def _register_default_codecs(self):
        """Register default codec handlers."""
        # H.264
        self.register("h264", H264Handler(), aliases=["h.264", "x264"])
        # H.265
        self.register("h265", H265Handler(), aliases=["h.265", "hevc", "x265"])
        # VP8
        self.register("vp8", VP8Handler())
        # VP9
        self.register("vp9", VP9Handler())
        # AV1
        self.register("av1", AV1Handler(), aliases=["aom"])
        # MPEG-4
        self.register("mpeg4", MPEG4Handler(), aliases=["mpeg-4"])

    def register(
        self,
        name: str,
        handler: CodecHandler,
        aliases: Optional[List[str]] = None,
    ):
        """Register a codec handler."""
        self._handlers[name.lower()] = handler
        if aliases:
            for alias in aliases:
                self._aliases[alias.lower()] = name.lower()

    def get_handler(self, codec_name: str) -> Optional[CodecHandler]:
        """Get codec handler by name or alias."""
        codec_name = codec_name.lower()
        # Check direct name
        if codec_name in self._handlers:
            return self._handlers[codec_name]
        # Check aliases
        if codec_name in self._aliases:
            canonical_name = self._aliases[codec_name]
            return self._handlers.get(canonical_name)
        return None

    def check_codec_available(self, codec_name: str) -> bool:
        """Check if codec encoder is available in FFmpeg."""
        handler = self.get_handler(codec_name)
        if not handler:
            return False

        encoder = handler.get_encoder()
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                check=False,
            )
            return encoder in result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


# Global codec registry
CODEC_REGISTRY = CodecRegistry()


@dataclass
class VideoConfig:
    """Configuration for a single video generation task."""

    width: int
    height: int
    fps: int
    codec: str
    duration: float
    bitrate: Optional[str] = None
    pix_fmt: str = "yuv420p"
    test_pattern: str = "testsrc2"
    output_dir: Path = Path(".")
    output_filename: Optional[str] = None
    skip_existing: bool = True
    preset: str = "veryslow"
    bitrate_formula: Optional[str] = None
    extra_params: List[str] = field(default_factory=list)

    def validate(self):
        """Validate configuration."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Width and height must be positive")
        if self.fps <= 0:
            raise ValueError("FPS must be positive")
        if self.duration <= 0:
            raise ValueError("Duration must be positive")
        if not CODEC_REGISTRY.get_handler(self.codec):
            raise ValueError(f"Unsupported codec: {self.codec}")

    def get_output_path(self) -> Path:
        """Get the full output path for the video."""
        if self.output_filename:
            filename = self.output_filename
        else:
            handler = CODEC_REGISTRY.get_handler(self.codec)
            if not handler:
                raise ValueError(f"Unknown codec: {self.codec}")
            ext = handler.get_container()
            filename = f"{self.height}p_{self.fps}fps_{self.codec}.{ext}"

        return self.output_dir / filename

    def calculate_bitrate(self, formula: Optional[str] = None) -> str:
        """Calculate bitrate from formula."""
        formula = formula or self.bitrate_formula
        if not formula:
            # Default formula
            formula = DEFAULT_BITRATE_FORMULA

        # Security: Only allow safe arithmetic operations
        allowed_chars = set("0123456789+-*/.()abcdefghijklmnopqrstuvwxyz_ ")
        if not all(c in allowed_chars for c in formula.lower()):
            raise ValueError("Invalid characters in bitrate formula")

        # Block dangerous patterns
        dangerous = ["import", "exec", "eval", "__", "open", "file"]
        if any(d in formula.lower() for d in dangerous):
            raise ValueError("Dangerous pattern detected in bitrate formula")

        # Evaluate with only width, height, fps in scope
        try:
            result = eval(
                formula,
                {"__builtins__": {}},
                {"width": self.width, "height": self.height, "fps": self.fps},
            )
            # Convert to bitrate string (bits per second)
            if result >= 1000000:
                return f"{int(result / 1000000)}M"
            elif result >= 1000:
                return f"{int(result / 1000)}k"
            else:
                return f"{int(result)}"
        except Exception as e:
            raise ValueError(f"Error evaluating bitrate formula: {e}")

    def get_bitrate(self, global_formula: Optional[str] = None) -> str:
        """Get bitrate, calculating if needed."""
        if self.bitrate:
            return self.bitrate

        formula = self.bitrate_formula or global_formula
        return self.calculate_bitrate(formula)


def parse_resolution(
    resolution: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Tuple[int, int]:
    """Parse resolution from various formats."""
    if width and height:
        return (width, height)

    if not resolution:
        raise ValueError(
            "Resolution must be provided (--resolution or --width/--height)"
        )

    # Check presets
    resolution_upper = resolution.upper()
    if resolution_upper in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[resolution_upper]

    # Parse explicit format (e.g., "1920x1080" or "1920:1080")
    match = re.match(r"^(\d+)[x:](\d+)$", resolution)
    if match:
        return (int(match.group(1)), int(match.group(2)))

    raise ValueError(f"Invalid resolution format: {resolution}")


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from JSON or YAML file."""
    with open(config_path, "r") as f:
        if config_path.suffix.lower() in [".yaml", ".yml"]:
            if yaml is None:
                raise ImportError(
                    "PyYAML is required for YAML config files. "
                    "Install with: pip install pyyaml"
                )
            return yaml.safe_load(f)
        else:
            return json.load(f)


def validate_config(config: Dict[str, Any]):
    """Validate configuration structure."""
    if "videos" not in config:
        raise ValueError(
            "Config file must contain 'videos' key "
            "with a list of video configurations"
        )
    if not isinstance(config["videos"], list):
        raise ValueError("'videos' must be a list")
    if len(config["videos"]) == 0:
        raise ValueError("'videos' list cannot be empty")


def merge_configs(
    defaults: Dict[str, Any],
    video_config: Dict[str, Any],
    cli_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge configurations with priority:
    defaults < video_config < cli_overrides.
    """
    merged = {}
    # Start with defaults
    merged.update(defaults or {})
    # Override with video config
    merged.update(video_config)
    # Override with CLI arguments
    merged.update(cli_overrides)
    return merged


def build_ffmpeg_command(
    config: VideoConfig, global_bitrate_formula: Optional[str] = None
) -> List[str]:
    """Build FFmpeg command for video generation."""
    handler = CODEC_REGISTRY.get_handler(config.codec)
    if not handler:
        raise ValueError(f"Unknown codec: {config.codec}")

    # Calculate GOP size (2 seconds worth of frames)
    gop_size = int(config.fps * 2)

    # Get bitrate
    bitrate = config.get_bitrate(global_bitrate_formula)

    # Build command
    cmd = ["ffmpeg"]

    # Global reproducibility flags
    cmd.extend(["-bitexact", "-map_metadata", "-1", "-fflags", "+bitexact"])

    # Input (test pattern)
    test_pattern_str = (
        f"{config.test_pattern}=size={config.width}x{config.height}:"
        f"rate={config.fps}:duration={config.duration}"
    )
    cmd.extend(["-f", "lavfi", "-i", test_pattern_str])

    # Video codec and parameters
    cmd.extend(["-c:v", handler.get_encoder()])
    cmd.extend(["-pix_fmt", config.pix_fmt])
    cmd.extend(["-b:v", bitrate])
    cmd.extend(handler.get_speed_param(config.preset))
    cmd.extend(handler.get_essential_params(gop_size))
    cmd.extend(handler.get_codec_params())

    # Extra parameters
    cmd.extend(config.extra_params)

    # Output
    output_path = config.get_output_path()
    cmd.append(str(output_path))

    return cmd


def format_time(seconds: float) -> str:
    """Format time in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


def generate_video(
    config: VideoConfig, global_bitrate_formula: Optional[str] = None
) -> bool:
    """Generate a single video."""
    config.validate()

    output_path = config.get_output_path()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists and should be skipped
    if config.skip_existing and output_path.exists():
        print(f"Skipping {output_path.name} (already exists)")
        return False

    # Check codec availability
    handler = CODEC_REGISTRY.get_handler(config.codec)
    if not handler or not CODEC_REGISTRY.check_codec_available(config.codec):
        encoder_name = handler.get_encoder() if handler else config.codec
        print(
            f"ERROR: Codec encoder '{encoder_name}' is not available in FFmpeg"
        )
        return False

    # Build and run command
    cmd = build_ffmpeg_command(config, global_bitrate_formula)
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate reproducible golden video samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Resolution options (mutually exclusive)
    resolution_group = parser.add_mutually_exclusive_group()
    resolution_group.add_argument(
        "--resolution",
        type=str,
        help=(
            "Resolution preset (480p, 720p, 1080p, 2160p, 4K, 8K) "
            "or explicit (1920x1080)"
        ),
    )
    resolution_group.add_argument(
        "--width", type=int, help="Video width (use with --height)"
    )
    parser.add_argument(
        "--height", type=int, help="Video height (use with --width)"
    )

    # Required parameters (when not using --config)
    parser.add_argument("--fps", type=int, help="Frames per second")
    parser.add_argument(
        "--codec",
        type=str,
        help="Video codec (h264, h265, vp8, vp9, av1, mpeg4)",
    )
    parser.add_argument("--duration", type=float, help="Duration in seconds")

    # Optional parameters
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
        "--test-pattern",
        type=str,
        default="testsrc2",
        help="Test pattern (default: testsrc2)",
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
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file (JSON or YAML) for batch generation",
    )

    args = parser.parse_args()

    # Create CLI overrides dict (exclude None values)
    cli_overrides = {}
    if args.codec:
        cli_overrides["codec"] = args.codec
    if args.fps is not None:
        cli_overrides["fps"] = args.fps
    if args.duration is not None:
        cli_overrides["duration"] = args.duration
    if args.bitrate:
        cli_overrides["bitrate"] = args.bitrate
    if args.pix_fmt:
        cli_overrides["pix_fmt"] = args.pix_fmt
    if args.test_pattern:
        cli_overrides["test_pattern"] = args.test_pattern
    if args.preset:
        cli_overrides["preset"] = args.preset
    if args.output_dir:
        cli_overrides["output_dir"] = Path(args.output_dir)
    if args.output_filename:
        cli_overrides["output_filename"] = args.output_filename
    if args.no_skip_existing:
        cli_overrides["skip_existing"] = False

    if args.config:
        # Batch mode: load config file
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: Config file not found: {config_path}")
            sys.exit(1)

        config_data = load_config(config_path)
        validate_config(config_data)

        defaults = config_data.get("defaults", {})
        global_bitrate_formula = config_data.get("bitrate_formula")

        videos = config_data["videos"]
        total = len(videos)
        success_count = 0

        for idx, video_data in enumerate(videos, 1):
            # Merge configurations
            merged = merge_configs(defaults, video_data, cli_overrides)

            # Parse resolution
            try:
                if "width" in merged and "height" in merged:
                    width, height = merged["width"], merged["height"]
                elif "resolution" in merged:
                    width, height = parse_resolution(
                        resolution=merged["resolution"]
                    )
                else:
                    # Try CLI args as fallback
                    width, height = parse_resolution(
                        args.resolution, args.width, args.height
                    )
            except ValueError as e:
                print(
                    f"ERROR: Video {idx}/{total} has invalid resolution: {e}"
                )
                continue

            # Create VideoConfig
            output_dir = Path(merged.get("output_dir", args.output_dir or "."))
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            video_config = VideoConfig(
                width=width,
                height=height,
                fps=merged.get("fps") or args.fps,
                codec=merged.get("codec") or args.codec,
                duration=merged.get("duration") or args.duration,
                bitrate=merged.get("bitrate"),
                pix_fmt=merged.get("pix_fmt", "yuv420p"),
                test_pattern=merged.get("test_pattern", "testsrc2"),
                output_dir=output_dir,
                output_filename=merged.get("output_filename"),
                skip_existing=merged.get("skip_existing", True),
                preset=merged.get("preset", "veryslow"),
                bitrate_formula=merged.get("bitrate_formula"),
                extra_params=merged.get("extra_params", []),
            )

            if (
                video_config.fps is None
                or video_config.codec is None
                or video_config.duration is None
            ):
                print(
                    f"ERROR: Video {idx}/{total} is missing required fields "
                    f"(fps, codec, duration)"
                )
                continue

            print(f"\n[{idx}/{total}] Processing video configuration...")
            if generate_video(video_config, global_bitrate_formula):
                success_count += 1

        print(f"\n✓ Generated {success_count}/{total} videos successfully")
        sys.exit(0 if success_count == total else 1)

    else:
        # Single video mode: use CLI arguments
        if not args.resolution and not (args.width and args.height):
            parser.error("--resolution or --width/--height is required")
        if not args.fps:
            parser.error("--fps is required")
        if not args.codec:
            parser.error("--codec is required")
        if not args.duration:
            parser.error("--duration is required")

        width, height = parse_resolution(
            args.resolution, args.width, args.height
        )

        output_dir = Path(args.output_dir)
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        config = VideoConfig(
            width=width,
            height=height,
            fps=args.fps,
            codec=args.codec,
            duration=args.duration,
            bitrate=args.bitrate,
            pix_fmt=args.pix_fmt,
            test_pattern=args.test_pattern,
            output_dir=output_dir,
            output_filename=args.output_filename,
            skip_existing=not args.no_skip_existing,
            preset=args.preset,
            extra_params=[],
        )

        success = generate_video(config)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
