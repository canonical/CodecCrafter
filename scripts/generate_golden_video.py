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
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
)

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


def _base_essential_params(
    gop_size: int,
    *,
    sc_threshold: bool = False,
    keyint_min: bool = True,
) -> List[str]:
    """Return common essential params: threads, g, keyint_min, sc_threshold."""
    params = ["-threads", "1", "-g", str(gop_size)]
    if keyint_min:
        params.extend(["-keyint_min", str(gop_size)])
    if sc_threshold:
        params.extend(["-sc_threshold", "0"])
    return params


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


def _speed_param(speed_type: str, preset: str) -> List[str]:
    """Return speed params by type: preset, cpu_used, or none."""
    if speed_type == "preset":
        return ["-preset", preset]
    if speed_type == "cpu_used":
        return ["-cpu-used", "0"]
    return []


class ConfigurableCodecHandler(CodecHandler):
    """Codec handler driven by config (encoder, container, options)."""

    def __init__(
        self,
        encoder: str,
        container: str,
        *,
        speed_type: str = "none",
        sc_threshold: bool = False,
        keyint_min: bool = True,
        extra_essential: Optional[List[str]] = None,
        codec_params: Optional[List[str]] = None,
    ):
        super().__init__(encoder, container)
        self._speed_type = speed_type
        self._sc_threshold = sc_threshold
        self._keyint_min = keyint_min
        self._extra_essential = extra_essential or []
        self._codec_params = codec_params or []

    def get_speed_param(self, preset: str) -> List[str]:
        return _speed_param(self._speed_type, preset)

    def get_essential_params(self, gop_size: int) -> List[str]:
        base = _base_essential_params(
            gop_size,
            sc_threshold=self._sc_threshold,
            keyint_min=self._keyint_min,
        )
        return base + self._extra_essential

    def get_codec_params(self) -> List[str]:
        return self._codec_params.copy()


class CodecConfigSchema(BaseModel):
    """Schema for a single codec configuration (from codecs.yaml)."""

    model_config = ConfigDict(extra="forbid")

    encoder: str
    container: str
    speed_type: Literal["preset", "cpu_used", "none"] = "none"
    sc_threshold: bool = False
    keyint_min: bool = True
    extra_essential: List[str] = []
    codec_params: List[str] = []
    aliases: List[str] = []


def _load_codec_configs() -> Dict[str, CodecConfigSchema]:
    """Load and validate codec configs from YAML."""
    config_path = Path(__file__).parent / "config" / "codecs.yaml"
    with open(config_path, "r") as f:
        if yaml is None:
            raise ImportError(
                "PyYAML is required for codec config. "
                "Install with: pip install pyyaml"
            )
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError("codecs.yaml must be a dict mapping names to configs")
    result = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"Codec '{name}' config must be a dict")
        result[name] = CodecConfigSchema.model_validate(cfg)
    return result


CODEC_CONFIGS: Dict[str, CodecConfigSchema] = _load_codec_configs()


class CodecRegistry:
    """Registry for codec handlers."""

    def __init__(self):
        self._handlers: Dict[str, CodecHandler] = {}
        self._aliases: Dict[str, str] = {}
        self._register_default_codecs()

    def _register_default_codecs(self):
        """Register default codec handlers from CODEC_CONFIGS."""
        for name, cfg in CODEC_CONFIGS.items():
            handler = ConfigurableCodecHandler(
                encoder=cfg.encoder,
                container=cfg.container,
                speed_type=cfg.speed_type,
                sc_threshold=cfg.sc_threshold,
                keyint_min=cfg.keyint_min,
                extra_essential=cfg.extra_essential,
                codec_params=cfg.codec_params,
            )
            self.register(name, handler, aliases=cfg.aliases or None)

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


class BaseVideoConfig(BaseModel):
    """Configuration for a single video generation task (shared fields)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    width: int
    height: int
    fps: int
    codec: str
    duration: float
    bitrate: Optional[str] = None
    pix_fmt: str = "yuv420p"
    output_dir: Path = Path(".")
    output_filename: Optional[str] = None
    skip_existing: bool = True
    preset: str = "veryslow"
    bitrate_formula: Optional[str] = None
    extra_params: List[str] = []

    @field_validator("width", "height")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        if not CODEC_REGISTRY.get_handler(v):
            raise ValueError(f"Unsupported codec: {v}")
        return v

    def get_filename_suffix(self) -> str:
        """Return filename suffix (override in subclasses, e.g. '_avsync')."""
        return ""

    def get_output_path(self) -> Path:
        """Get the full output path for the video."""
        if self.output_filename:
            filename = self.output_filename
        else:
            handler = CODEC_REGISTRY.get_handler(self.codec)
            if not handler:
                raise ValueError(f"Unknown codec: {self.codec}")
            ext = handler.get_container()
            suffix = self.get_filename_suffix()
            base = f"{self.height}p_{self.fps}fps_{self.codec}"
            filename = f"{base}{suffix}.{ext}"

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

    def _build_encoding_args(
        self,
        handler: CodecHandler,
        global_bitrate_formula: Optional[str] = None,
    ) -> List[str]:
        """Return common encoding args for video."""
        gop_size = int(self.fps * 2)
        bitrate = self.get_bitrate(global_bitrate_formula)
        enc = [
            "-c:v",
            handler.get_encoder(),
            "-pix_fmt",
            self.pix_fmt,
            "-b:v",
            bitrate,
        ]
        return (
            enc
            + handler.get_speed_param(self.preset)
            + handler.get_essential_params(gop_size)
            + handler.get_codec_params()
        )

    def build_ffmpeg_command(
        self, global_bitrate_formula: Optional[str] = None
    ) -> List[str]:
        """Build FFmpeg command for this config. Subclasses must override."""
        raise NotImplementedError


class TestPatternVideoConfig(BaseVideoConfig):
    """Configuration for golden videos using lavfi test sources (testsrc2)."""

    test_pattern: str = "testsrc2"

    def build_ffmpeg_command(
        self, global_bitrate_formula: Optional[str] = None
    ) -> List[str]:
        """Build FFmpeg command for test pattern scenario."""
        handler = CODEC_REGISTRY.get_handler(self.codec)
        if not handler:
            raise ValueError(f"Unknown codec: {self.codec}")

        cmd = ["ffmpeg"]
        cmd.extend(["-bitexact", "-fflags", "+bitexact"])

        test_pattern_str = (
            f"{self.test_pattern}=size={self.width}x{self.height}:"
            f"rate={self.fps}:duration={self.duration}"
        )
        cmd.extend(["-f", "lavfi", "-i", test_pattern_str])

        cmd.extend(self._build_encoding_args(handler, global_bitrate_formula))
        cmd.extend(["-map_metadata", "-1"])
        cmd.extend(self.extra_params)
        cmd.append(str(self.get_output_path()))

        return cmd


class AvSyncVideoConfig(BaseVideoConfig):
    """Configuration for AV sync test videos (beep every second)."""

    audio_frequency: int = 1000
    beep_duration: float = 0.1

    @field_validator("duration")
    @classmethod
    def validate_duration_av_sync(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be positive")
        if v < 0.1:
            raise ValueError("AV sync scenario requires duration >= 0.1 seconds")
        return v

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
        self, global_bitrate_formula: Optional[str] = None
    ) -> List[str]:
        """Build FFmpeg command for AV sync scenario."""
        handler = CODEC_REGISTRY.get_handler(self.codec)
        if not handler:
            raise ValueError(f"Unknown codec: {self.codec}")

        cmd = ["ffmpeg"]

        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={self.width}x{self.height}:"
                f"d={self.duration}:r={self.fps}",
            ]
        )
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"aevalsrc=0:d={self.duration}:s=48000",
            ]
        )
        sine_spec = (
            f"sine=frequency={self.audio_frequency}:" f"duration={self.beep_duration}"
        )
        cmd.extend(["-f", "lavfi", "-i", sine_spec])

        filter_complex = self._build_filter_complex()
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[v]", "-map", "[a]"])

        cmd.extend(self._build_encoding_args(handler, global_bitrate_formula))

        container = handler.get_container()
        if container == "mp4":
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.extend(["-c:a", "libopus"])
        cmd.extend(["-b:a", "128k"])
        cmd.extend(["-t", str(self.duration)])
        cmd.append(str(self.get_output_path()))

        return cmd


# Scenario registry: config class, extra kwargs, forbidden keys per scenario
SCENARIO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "test_pattern": {
        "config_class": TestPatternVideoConfig,
        "extra_kwargs": ["test_pattern"],
        "extra_defaults": {"test_pattern": "testsrc2"},
        "forbidden_keys": {"audio_frequency", "beep_duration"},
    },
    "av_sync": {
        "config_class": AvSyncVideoConfig,
        "extra_kwargs": ["audio_frequency", "beep_duration"],
        "extra_defaults": {"audio_frequency": 1000, "beep_duration": 0.1},
        "forbidden_keys": {"test_pattern"},
    },
}


def create_config_from_merged(
    merged: Dict[str, Any],
    width: int,
    height: int,
    output_dir: Path,
) -> BaseVideoConfig:
    """Build video config from merged dict (used by batch and CLI)."""
    scenario = merged.get("scenario", "test_pattern")
    if scenario not in SCENARIO_REGISTRY:
        raise ValueError(
            f"Unknown scenario: {scenario}. "
            f"Must be one of: {sorted(SCENARIO_REGISTRY.keys())}"
        )

    spec = SCENARIO_REGISTRY[scenario]
    config_class = spec["config_class"]
    extra_defaults = spec["extra_defaults"]

    base_kwargs = {
        "width": width,
        "height": height,
        "fps": merged["fps"],
        "codec": merged["codec"],
        "duration": merged["duration"],
        "bitrate": merged.get("bitrate"),
        "pix_fmt": merged.get("pix_fmt", "yuv420p"),
        "output_dir": output_dir,
        "output_filename": merged.get("output_filename"),
        "skip_existing": merged.get("skip_existing", True),
        "preset": merged.get("preset", "veryslow"),
        "bitrate_formula": merged.get("bitrate_formula"),
        "extra_params": merged.get("extra_params", []),
    }

    extra_kwargs = {k: merged.get(k, extra_defaults[k]) for k in spec["extra_kwargs"]}

    return config_class(**base_kwargs, **extra_kwargs)


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

    # Check presets (case-insensitive)
    resolution_lower = resolution.lower()
    if resolution_lower in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[resolution_lower]
    # Also check uppercase for "4K", "UHD", "8K"
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


def validate_config_for_scenario(config: Dict[str, Any]) -> None:
    """Validate scenario-specific args (no cross-scenario keys)."""
    defaults = config.get("defaults", {})
    scenario = defaults.get("scenario", "test_pattern")

    if scenario not in SCENARIO_REGISTRY:
        allowed = sorted(SCENARIO_REGISTRY.keys())
        raise ValueError(f"defaults.scenario must be one of: {allowed}")

    forbidden_keys = SCENARIO_REGISTRY[scenario]["forbidden_keys"]

    def check_keys(d: Dict[str, Any], label: str) -> None:
        keys = set(d.keys())
        bad = keys & forbidden_keys
        if bad:
            raise ValueError(
                f"{label}: scenario '{scenario}' cannot have {sorted(bad)}"
            )

    check_keys(defaults, "defaults")

    for idx, video in enumerate(config["videos"]):
        check_keys(video, f"videos[{idx}]")


def merge_configs(
    defaults: Dict[str, Any],
    video_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge configurations with priority: defaults < video_config."""
    merged = {}
    merged.update(defaults or {})
    merged.update(video_config)
    return merged


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
    config: BaseVideoConfig,
    global_bitrate_formula: Optional[str] = None,
) -> bool:
    """Generate a single video."""
    output_path = config.get_output_path()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if config.skip_existing and output_path.exists():
        print(f"Skipping {output_path.name} (already exists)")
        return False

    handler = CODEC_REGISTRY.get_handler(config.codec)
    if not handler or not CODEC_REGISTRY.check_codec_available(config.codec):
        encoder_name = handler.get_encoder() if handler else config.codec
        print(f"ERROR: Codec encoder '{encoder_name}' " "is not available in FFmpeg")
        return False

    cmd = config.build_ffmpeg_command(global_bitrate_formula)
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
    parser.add_argument("--height", type=int, help="Video height (use with --width)")
    parser.add_argument("--fps", type=int, required=True, help="Frames per second")
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
    parser.add_argument("--bitrate", type=str, help="Bitrate (e.g., '40M', '5000k')")
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


def run_batch(args: argparse.Namespace) -> int:
    """Run batch mode: config-driven only, no CLI overrides."""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    config_data = load_config(config_path)
    try:
        validate_config(config_data)
        validate_config_for_scenario(config_data)
    except ValueError as e:
        print(f"ERROR: Config validation failed: {e}")
        return 1

    defaults = config_data.get("defaults", {})
    # Override output_dir from batch --output-dir
    defaults = dict(defaults, output_dir=Path(args.output_dir))
    global_bitrate_formula = config_data.get("bitrate_formula")

    videos = config_data["videos"]
    total = len(videos)
    success_count = 0

    for idx, video_data in enumerate(videos, 1):
        merged = merge_configs(defaults, video_data)

        try:
            if "width" in merged and "height" in merged:
                width, height = merged["width"], merged["height"]
            elif "resolution" in merged:
                res = merged["resolution"]
                width, height = parse_resolution(resolution=res)
            else:
                print(
                    f"ERROR: Video {idx}/{total} missing resolution or " "width/height"
                )
                continue
        except ValueError as e:
            print(f"ERROR: Video {idx}/{total} has invalid resolution: {e}")
            continue

        output_dir = Path(merged.get("output_dir", args.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)

        fps = merged.get("fps")
        codec = merged.get("codec")
        duration = merged.get("duration")
        if fps is None or codec is None or duration is None:
            print(
                f"ERROR: Video {idx}/{total} is missing required fields "
                "(fps, codec, duration)"
            )
            continue

        merged_with_dims = dict(merged, width=width, height=height)

        try:
            video_config = create_config_from_merged(
                merged_with_dims, width, height, output_dir
            )
        except ValidationError as e:
            print(f"ERROR: Video {idx}/{total} config invalid: {e}")
            continue

        print(f"\n[{idx}/{total}] Processing video configuration...")
        if generate_video(video_config, global_bitrate_formula):
            success_count += 1

    print(f"\n✓ Generated {success_count}/{total} videos successfully")
    return 0 if success_count == total else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate reproducible golden video samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # test_pattern subcommand
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

    # av_sync subcommand
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

    # batch subcommand
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

    args = parser.parse_args()

    if args.command == "batch":
        sys.exit(run_batch(args))

    sys.exit(run_single_video(args, sp_test, sp_av))


def run_single_video(
    args: argparse.Namespace,
    sp_test: argparse.ArgumentParser,
    sp_av: argparse.ArgumentParser,
) -> int:
    """Run single video generation (test_pattern or av_sync)."""
    if not args.resolution and not (args.width and args.height):
        subparser = sp_test if args.command == "test_pattern" else sp_av
        subparser.error("--resolution or --width/--height is required")

    width, height = parse_resolution(args.resolution, args.width, args.height)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        video_config = _build_config_from_args(args, width, height, output_dir)
    except ValidationError as e:
        print(f"ERROR: Invalid config: {e}")
        return 1

    success = generate_video(video_config)
    return 0 if success else 1


def _build_config_from_args(
    args: argparse.Namespace,
    width: int,
    height: int,
    output_dir: Path,
) -> BaseVideoConfig:
    """Build video config from CLI args for test_pattern or av_sync."""
    merged = {
        "width": width,
        "height": height,
        "fps": args.fps,
        "codec": args.codec,
        "duration": args.duration,
        "bitrate": args.bitrate,
        "pix_fmt": args.pix_fmt,
        "output_dir": output_dir,
        "output_filename": args.output_filename,
        "skip_existing": not args.no_skip_existing,
        "preset": args.preset,
        "extra_params": [],
        "scenario": args.command,
    }
    spec = SCENARIO_REGISTRY[args.command]
    for key in spec["extra_kwargs"]:
        merged[key] = getattr(args, key)

    return create_config_from_merged(merged, width, height, output_dir)


if __name__ == "__main__":
    main()
