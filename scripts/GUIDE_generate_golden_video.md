# Golden Video Generator - User Guide

## Introduction & Purpose

The `generate_golden_video.py` script generates reproducible golden video samples with configurable parameters. It supports multiple codecs (H.264, H.265, VP8, VP9, AV1, MPEG-4) with maximum reproducibility settings for consistent, bit-exact output across different machines and runs.

### Key Features

- **Reproducibility**: Bit-exact output across different machines and runs
- **Multiple Codecs**: H.264, H.265, VP8, VP9, AV1, MPEG-4
- **Config Defaults**: Define defaults for batch processing
- **Bitrate Formula**: Customizable bitrate calculation formulas
- **CLI Overrides**: Override config values from command line
- **Human-Readable Time**: Formatted time display for elapsed time
- **Extensible Architecture**: Easy to add new codecs and parameters

## Installation & Requirements

### Requirements

- Python 3.8+
- FFmpeg with support for desired codecs:
  - `libx264` for H.264
  - `libx265` for H.265
  - `libvpx` for VP8
  - `libvpx-vp9` for VP9
  - `libaom-av1` for AV1
  - `mpeg4` for MPEG-4
- PyYAML (for YAML config file support)

### Installation

#### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer. Install it first:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or with pip:
```bash
pip install uv
```

Then install dependencies:
```bash
uv pip install -r requirements.txt
```

#### Using pip (Alternative)

```bash
pip install -r requirements.txt
```

### Running the Script

No installation required - just run the script directly:

```bash
python3 scripts/generate_golden_video.py --help
```

Or make it executable:

```bash
chmod +x scripts/generate_golden_video.py
./scripts/generate_golden_video.py --help
```

Or with uv:

```bash
uv run python scripts/generate_golden_video.py --help
```

## Command Structure

The script uses **subcommands**. You must specify one of:

- **`test_pattern`** — Generate golden videos with lavfi test sources (testsrc2)
- **`av_sync`** — Generate AV sync test videos (black background, white flash + beep every second)
- **`batch`** — Batch generation from a config file

## Quick Start Examples

### Single Video via CLI

```bash
# test_pattern: Generate 1080p H.264 video with test pattern
./scripts/generate_golden_video.py test_pattern --resolution 1080p --fps 60 --codec h264 --duration 10

# test_pattern: Generate UHD (2160p) video
./scripts/generate_golden_video.py test_pattern --resolution 2160p --fps 30 --codec h265 --duration 10

# test_pattern: Generate true 4K (4096×2160) video
./scripts/generate_golden_video.py test_pattern --resolution 4K --fps 30 --codec vp9 --duration 10 --bitrate 120M

# test_pattern: Generate AV1 video
./scripts/generate_golden_video.py test_pattern --resolution 1080p --fps 30 --codec av1 --duration 10

# av_sync: Generate AV sync test video (beep every second)
./scripts/generate_golden_video.py av_sync --resolution 1080p --fps 30 --codec h264 --duration 10
```

### Batch Generation from Config File

```bash
# Simple batch (test_pattern scenario)
./scripts/generate_golden_video.py batch --config example_config/example_simple.json --output-dir video

# Advanced batch with defaults
./scripts/generate_golden_video.py batch --config example_config/example_advanced.json --output-dir video

# AV sync test videos
./scripts/generate_golden_video.py batch --config scripts/config/golden_sample_av_sync_testset.yaml --output-dir video
```

**Note:** Batch mode is config-driven only. The config file must set `defaults.scenario` to `test_pattern` or `av_sync`. There are no CLI overrides for batch.

## Configuration File Format

### Required Structure

The config file **must** use the new format with a `videos` array:

```json
{
  "videos": [
    {
      "resolution": "1080p",
      "fps": 60,
      "codec": "h264",
      "duration": 10
    }
  ],
  "defaults": {
    "scenario": "test_pattern",
    "pix_fmt": "yuv420p",
    "test_pattern": "testsrc2"
  },
  "bitrate_formula": "width * height * fps * 0.1"
}
```

**Important**: The old format (list or single dict) is **not supported**. You must use the new format with `videos` array.

### Scenario

Batch configs must specify `defaults.scenario`:

- **`test_pattern`** — Lavfi test sources (testsrc2). Output filenames: `{height}p_{fps}fps_{codec}.{ext}`
- **`av_sync`** — Black background, white flash + beep every second. Output filenames: `{height}p_{fps}fps_{codec}_avsync.{ext}`

Each config file targets **one scenario**. Scenario-specific keys cannot be mixed (e.g., `test_pattern` configs cannot have `audio_frequency`; `av_sync` configs cannot have `test_pattern`).

### Field Reference

#### Required Fields (per video)

- `resolution`: Resolution string (e.g., "1080p", "2160p", "4K", "1920x1080") OR
- `width` + `height`: Explicit dimensions as integers
- `fps`: Frames per second (integer)
- `codec`: Codec name (string, see Supported Codecs below)
- `duration`: Duration in seconds (float)

#### Optional Fields (per video)

- `bitrate`: Bitrate string (e.g., "40M", "5000k"). Auto-calculated if not provided
- `pix_fmt`: Pixel format (default: "yuv420p")
- `output_dir`: Output directory path (string or Path)
- `output_filename`: Custom output filename (string)
- `skip_existing`: Skip if file exists (boolean, default: true)
- `preset`: FFmpeg preset (default: "veryslow")
- `bitrate_formula`: Custom bitrate formula (string, overrides global formula)
- `extra_params`: Additional FFmpeg parameters (list of strings)

**Scenario-specific (test_pattern only):**

- `test_pattern`: FFmpeg test pattern (default: "testsrc2")

**Scenario-specific (av_sync only):**

- `audio_frequency`: Sine beep frequency in Hz (default: 1000)
- `beep_duration`: Beep duration in seconds (default: 0.1)

#### Defaults Section

The `defaults` section is optional and applies to all videos:

```json
{
  "defaults": {
    "scenario": "test_pattern",
    "pix_fmt": "yuv420p",
    "test_pattern": "testsrc2",
    "preset": "veryslow"
  }
}
```

For `av_sync`:

```json
{
  "defaults": {
    "scenario": "av_sync",
    "pix_fmt": "yuv420p",
    "audio_frequency": 1000,
    "beep_duration": 0.1
  }
}
```

#### Global Bitrate Formula

The `bitrate_formula` at root level is optional and applies to all videos that don't have their own `bitrate` or `bitrate_formula`:

```json
{
  "bitrate_formula": "width * height * fps * 0.15"
}
```

### Examples

See the example files in the `example_config/` directory:
- `example_config/example_simple.json` - Simple batch
- `example_config/example_batch.json` - Multiple videos with defaults
- `example_config/example_advanced.json` - Advanced with bitrate formulas
- `example_config/example_av1.json` - AV1 examples
- `example_config/example.yaml` - YAML format

For detailed configuration documentation, see `example_config/GUIDE_config.md`.

## Command-Line Interface

### Subcommands

| Subcommand | Description |
|------------|--------------|
| `test_pattern` | Generate golden videos with lavfi test sources |
| `av_sync` | Generate AV sync test videos (beep every second) |
| `batch` | Batch generation from config file |

### Common Options (test_pattern and av_sync)

#### Resolution Options (mutually exclusive)

- `--resolution RESOLUTION`: Resolution preset or explicit format
  - Presets: `480p`, `720p`, `1080p`, `2160p`/`UHD` (3840×2160), `4K` (4096×2160), `8K` (7680×4320)
  - Explicit: `1920x1080` or `1920:1080`
- `--width WIDTH`: Video width in pixels (use with `--height`)
- `--height HEIGHT`: Video height in pixels (use with `--width`)

#### Required Parameters

- `--fps FPS`: Frames per second
- `--codec CODEC`: Video codec (see Supported Codecs)
- `--duration DURATION`: Duration in seconds

#### Optional Parameters

- `--bitrate BITRATE`: Bitrate (e.g., "40M", "5000k"). Auto-calculated if not provided
- `--pix-fmt PIX_FMT`: Pixel format (default: "yuv420p")
- `--preset PRESET`: FFmpeg preset (default: "veryslow")
- `--output-dir DIR`: Output directory (default: current directory)
- `--output-filename FILENAME`: Output filename (auto-generated if not provided)
- `--no-skip-existing`: Overwrite existing files instead of skipping

#### test_pattern-only

- `--test-pattern PATTERN`: FFmpeg test pattern (default: "testsrc2")

#### av_sync-only

- `--audio-frequency HZ`: Sine beep frequency in Hz (default: 1000)
- `--beep-duration SEC`: Beep duration in seconds (default: 0.1)

### Batch Options

- `--config PATH`: Configuration file (JSON or YAML) — **required**
- `--output-dir DIR`: Output directory for generated videos — **required**

## Bitrate Formula

### Syntax

The bitrate formula allows custom calculation of bitrate based on video parameters.

**Variables**:
- `width`: Video width in pixels
- `height`: Video height in pixels
- `fps`: Frames per second

**Operators**: `+`, `-`, `*`, `/`, `**` (exponentiation), parentheses

### Examples

```json
{
  "bitrate_formula": "width * height * fps * 0.1"
}
```

```json
{
  "bitrate_formula": "width * height * fps * 0.15"
}
```

```json
{
  "bitrate_formula": "(width * height * fps) / 1000000 * 8"
}
```

### Security

The formula evaluation is restricted to arithmetic operations only. Dangerous patterns (like `import`, `exec`, `eval`) are rejected.

## Reproducibility Features

### Complete Reproducibility Specification

The script implements **complete reproducibility settings** for bit-exact output across different machines and runs.

#### A. Global FFmpeg Flags

These flags are applied to **all codecs** and strip non-deterministic metadata:

```bash
-bitexact -map_metadata -1 -fflags +bitexact
```

These flags ensure that metadata (like "Encoded date" or "Writing library version") doesn't change between runs.

#### B. Codec-Specific Parameters

| **Codec** | **Library** | **Speed Parameter** | **Essential Parameters** | **Codec-Specific Params** |
|-----------|-------------|---------------------|-------------------------|---------------------------|
| **VP8** | `libvpx` | `-cpu-used 0` | `-threads 1`, `-g <val>`, `-keyint_min <val>` | _(None)_ |
| **VP9** | `libvpx-vp9` | `-cpu-used 0` | `-threads 1`, `-g <val>`, `-keyint_min <val>`, `-tile-columns 0`, `-tile-rows 0`, `-row-mt 0` | _(None)_ |
| **H.264** | `libx264` | `-preset veryslow` | `-threads 1`, `-g <val>`, `-keyint_min <val>`, `-sc_threshold 0` | `deterministic=1`, `no-mbtree=1`, `no-mixed-refs=1` |
| **H.265** | `libx265` | `-preset veryslow` | `-threads 1`, `-g <val>`, `-keyint_min <val>`, `-sc_threshold 0` | `deterministic=1`, `no-open-gop=1`, `no-wpp=1`, `no-pmode=1`, `no-pme=1` |
| **AV1** | `libaom-av1` | `-cpu-used 0` | `-threads 1`, `-g <val>`, `-keyint_min <val>` | _(None)_ |
| **MPEG-4** | `mpeg4` | _(N/A)_ | `-threads 1`, `-g <val>` | _(None)_ |

#### C. Critical Rules for Deterministic Output

1. **GOP Structure**: `-g` and `-keyint_min` **MUST** be the same value
   - Calculated as: `gop_size = fps * 2` (2 seconds worth of frames)
   - Example: 30 fps → `-g 60 -keyint_min 60`

2. **Thread Count**: Always `-threads 1` for all codecs

3. **x265 Strict Determinism**: Must disable all parallel processing:
   - `no-wpp=1`: Disables Wavefront Parallel Processing (major source of variance)
   - `no-pmode=1`: Disables Parallel Mode Decision
   - `no-pme=1`: Disables Parallel Motion Estimation

4. **VP9 Strict Determinism**: Must disable tiling and row multithreading:
   - `-tile-columns 0`: Forces whole frame encoding (slower, but deterministic)
   - `-tile-rows 0`: Disables row tiling
   - `-row-mt 0`: Disables row-based multithreading

5. **AV1 Notes**: 
   - AV1 is generally more deterministic by default
   - Still requires `-threads 1` and fixed GOP
   - Container: `.webm`

### Verification Checklist

To verify that your output is bit-exact (identical file hash):

1. ✅ **Force Single Thread**: `-threads 1` is set
2. ✅ **Strip Metadata**: Global flags (`-bitexact -map_metadata -1 -fflags +bitexact`) are present
3. ✅ **Lock the GOP**: `-g` and `-keyint_min` are the same value
4. ✅ **Disable Advanced Parallelism**: 
   - x265: `no-wpp=1`, `no-pmode=1`, `no-pme=1`
   - VP9: `-tile-columns 0`, `-tile-rows 0`, `-row-mt 0`
5. ✅ **Disable Scene Detection**: x264/x265 use `-sc_threshold 0`
6. ✅ **Deterministic Codec Params**: All codec-specific deterministic flags are set

### Why Reproducibility Matters

Reproducible video generation ensures:
- **Consistent Testing**: Same input produces same output across different machines
- **Regression Detection**: Changes in output indicate actual codec/encoder changes
- **Golden File Validation**: Reference videos can be verified with checksums
- **CI/CD Reliability**: Automated tests produce consistent results

## Supported Codecs

### Codec List

- **H.264**: `h264`, `h.264`, `x264`
- **H.265**: `h265`, `h.265`, `hevc`, `x265`
- **VP8**: `vp8`
- **VP9**: `vp9`
- **AV1**: `av1`, `aom`
- **MPEG-4**: `mpeg4`, `mpeg-4`

### Container Formats

- **VP8/VP9/AV1**: `.webm`
- **H.264/H.265/MPEG-4**: `.mp4`

### Codec Availability

The script checks for codec encoder availability before encoding. If a codec is not available, it will report an error.

## Extending the Script

### Adding a New Codec

Codecs are defined in `scripts/config/codecs.yaml` using a Pydantic-validated schema. To add a new codec, add an entry to that file:

```yaml
svt_av1:
  encoder: libsvtav1
  container: mp4
  speed_type: preset
  codec_params:
    - "-svtav1-params"
    - "tune=0"
  aliases: [svt-av1]
```

**Schema fields:**

- `encoder` (required): FFmpeg encoder name (e.g., `libx264`).
- `container` (required): Output container (e.g., `mp4`, `webm`).
- `speed_type`: `preset` | `cpu_used` | `none` (default: `none`).
- `sc_threshold`: `true` for x264/x265 (default: `false`).
- `keyint_min`: `false` for MPEG-4 (default: `true`).
- `extra_essential`: Extra FFmpeg args for reproducibility (see below). **Required for VP9**; omit for VP8, AV1, MPEG-4.
- `codec_params`: Codec-specific params passed to FFmpeg (see below).
- `aliases`: Alternative names (e.g., `[h.264, x264]`).

#### Understanding `codec_params`

`codec_params` is a list of strings passed **directly** to FFmpeg as arguments. Each entry becomes one argument. For options that take a value, use two entries: the option name and its value.

**Format:** `[option1, value1, option2, value2, ...]` or just `[option1, value1]` for a single option.

**Example 1 — H.264 (libx264):**

x264 uses `-x264-params` with a colon-separated `key=value` string:

```yaml
codec_params:
  - "-x264-params"
  - "deterministic=1:no-mbtree=1:no-mixed-refs=1"
```

This produces: `ffmpeg ... -x264-params deterministic=1:no-mbtree=1:no-mixed-refs=1 ...`

- `deterministic=1` — avoid non-deterministic encoder behavior
- `no-mbtree=1` — disable macroblock tree (reduces variance)
- `no-mixed-refs=1` — reduce reference-frame variance

**Example 2 — H.265 (libx265):**

x265 uses `-x265-params` with a similar format:

```yaml
codec_params:
  - "-x265-params"
  - "deterministic=1:no-open-gop=1:no-wpp=1:no-pmode=1:no-pme=1"
```

- `deterministic=1` — deterministic encoding
- `no-open-gop=1` — closed GOP for reproducibility
- `no-wpp=1`, `no-pmode=1`, `no-pme=1` — disable parallelism for reproducibility

**Example 3 — SVT-AV1 (libsvtav1):**

```yaml
codec_params:
  - "-svtav1-params"
  - "tune=0"
```

**Example 4 — No codec_params (VP8, AV1, MPEG-4):**

If the encoder does not need extra params, omit `codec_params` or leave it empty:

```yaml
vp8:
  encoder: libvpx
  container: webm
  speed_type: cpu_used
  # codec_params not needed
```

**Example 5 — VP9 (no codec_params, requires extra_essential):**

VP9 does not use `codec_params`, but it **requires** `extra_essential` for reproducibility:

```yaml
vp9:
  encoder: libvpx-vp9
  container: webm
  speed_type: cpu_used
  # codec_params not needed
  extra_essential:
    - "-tile-columns"
    - "0"
    - "-tile-rows"
    - "0"
    - "-row-mt"
    - "0"
```

See "Understanding extra_essential" below for why these options are required.

**How to find params for a new encoder:** Check the encoder's docs (e.g., `ffmpeg -h encoder=libx264`) or the project website. Look for reproducibility/determinism options.

#### Understanding `extra_essential`

`extra_essential` adds extra FFmpeg arguments for reproducibility. It uses the same format as FFmpeg: alternating option names and values.

**VP9 — required for reproducibility**

Without `extra_essential`, VP9 may use tiling and row multithreading, which can produce different bitstreams for the same input across runs. For reproducible golden videos, VP9 must include:

```yaml
vp9:
  encoder: libvpx-vp9
  container: webm
  speed_type: cpu_used
  extra_essential:
    - "-tile-columns"
    - "0"
    - "-tile-rows"
    - "0"
    - "-row-mt"
    - "0"
```

- `-tile-columns 0`, `-tile-rows 0` — disable frame tiling (VP9-specific)
- `-row-mt 0` — disable row-based multithreading

See [VP9 encoder options](https://ffmpeg.org/ffmpeg-codecs.html#libvpx_002c-libvpx_002dvp9) for details.

**VP8, AV1, MPEG-4 — omit when not needed**

These codecs do not require `extra_essential` for reproducibility:

- **VP8** — No tiling or row-mt options. See [libvpx VP8](https://www.webmproject.org/vp8/) and [FFmpeg libvpx](https://ffmpeg.org/ffmpeg-codecs.html#libvpx_002c-libvpx_002dvp9).
- **AV1** (libaom) — Generally deterministic by default. See [AOM AV1](https://aomedia.org/av1/) and [FFmpeg libaom-av1](https://ffmpeg.org/ffmpeg-codecs.html#libaom_002dav1).
- **MPEG-4** — Simple encoder without these options. See [FFmpeg mpeg4](https://ffmpeg.org/ffmpeg-codecs.html#mpeg4).

For these codecs, omit `extra_essential` or leave it empty.

### Adding a New Scenario

To add a new scenario:

1. Create a config class inheriting from `BaseVideoConfig` with `build_ffmpeg_command` and `get_filename_suffix`
2. Register in `SCENARIO_REGISTRY` with `config_class`, `extra_kwargs`, `extra_defaults`, `forbidden_keys`
3. Add a subparser in `main()` and wire `run_single_video` / `_build_config_from_args`
4. Update this guide and `example_config/GUIDE_config.md`

## Troubleshooting

### Common Issues

#### "Config file must contain 'videos' key"

**Problem**: You're using the old config format.

**Solution**: Convert to new format with `videos` array:

```json
{
  "videos": [
    {
      "resolution": "1080p",
      "fps": 30,
      "codec": "h264",
      "duration": 10
    }
  ]
}
```

#### "Codec encoder 'libx265' is not available"

**Problem**: FFmpeg doesn't have the required codec encoder installed.

**Solution**: Install FFmpeg with the required codec support. For example:
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Or compile FFmpeg with the required codec support

#### "Invalid bitrate formula"

**Problem**: The bitrate formula contains invalid characters or operations.

**Solution**: Use only arithmetic operations and variables (`width`, `height`, `fps`). Example:
```json
"bitrate_formula": "width * height * fps * 0.1"
```

#### Files are not bit-exact between runs

**Problem**: Reproducibility settings may not be fully applied.

**Solution**: 
1. Verify all reproducibility flags are present in the ffmpeg command (check debug logs)
2. Ensure `-g` and `-keyint_min` are the same value
3. For x265, verify `no-wpp=1`, `no-pmode=1`, `no-pme=1` are set
4. For VP9, verify `-tile-columns 0`, `-tile-rows 0`, `-row-mt 0` are set

## Migration from Old Scripts

### Config Format Conversion

**Old format (not supported)**:
```json
[
  {
    "resolution": "1080p",
    "fps": 60,
    "codec": "h264",
    "duration": 10
  }
]
```

**New format (required)**:
```json
{
  "videos": [
    {
      "resolution": "1080p",
      "fps": 60,
      "codec": "h264",
      "duration": 10
    }
  ]
}
```

### Field Name Changes

If migrating from older scripts:

- `format` → `codec`
- `output` → `output_filename`

**Old**:
```json
{
  "format": "h264",
  "output": "video.mp4"
}
```

**New**:
```json
{
  "codec": "h264",
  "output_filename": "video.mp4"
}
```

### Single Video Config

Even for a single video, use the `videos` array:

```json
{
  "videos": [
    {
      "resolution": "1080p",
      "fps": 30,
      "codec": "h264",
      "duration": 10
    }
  ]
}
```

## Additional Resources

- Configuration guide: `example_config/GUIDE_config.md`
- Example config files in `example_config/` directory
- FFmpeg documentation: https://ffmpeg.org/documentation.html
- Codec-specific documentation:
  - x264: https://www.videolan.org/developers/x264.html
  - x265: https://x265.readthedocs.io/
  - VP9: https://www.webmproject.org/vp9/
  - AV1: https://aomedia.org/av1/
