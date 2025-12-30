# Configuration File Guide

This guide explains how to write configuration files for the golden video generator.

## File Format

Configuration files can be written in either **JSON** or **YAML** format. Use `.json` or `.yaml`/`.yml` extensions.

## Required Structure

All configuration files **must** follow this structure:

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

The `videos` key is **required** and must contain an array of video configurations.

## Video Configuration Fields

### Required Fields

Each video in the `videos` array must have these fields:

#### Resolution (choose one)

- **`resolution`** (string): Resolution preset or explicit format
  - Presets: `480p`, `720p`, `1080p`, `2160p`/`UHD` (3840×2160), `4K` (4096×2160), `8K` (7680×4320)
  - Explicit: `1920x1080` or `1920:1080`
- **OR `width` + `height`** (integers): Explicit dimensions in pixels

#### Other Required Fields

- **`fps`** (integer): Frames per second (e.g., `30`, `60`)
- **`codec`** (string): Video codec name (see [Supported Codecs](#supported-codecs))
- **`duration`** (float): Duration in seconds (e.g., `10`, `5.5`)

### Optional Fields

- **`bitrate`** (string): Bitrate specification (e.g., `"40M"`, `"5000k"`). If not provided, will be calculated from formula.
- **`pix_fmt`** (string): Pixel format (default: `"yuv420p"`)
- **`test_pattern`** (string): FFmpeg test pattern (default: `"testsrc2"`)
- **`output_dir`** (string): Output directory path (default: current directory or `"video"`)
- **`output_filename`** (string): Custom output filename. If not provided, auto-generated as `{height}p_{fps}fps_{codec}.{ext}`
- **`skip_existing`** (boolean): Skip if file exists (default: `true`)
- **`preset`** (string): FFmpeg preset (default: `"veryslow"`)
- **`bitrate_formula`** (string): Custom bitrate formula for this video (overrides global formula)
- **`extra_params`** (array of strings): Additional FFmpeg parameters (e.g., `["-crf", "23"]`)

## Defaults Section

The `defaults` section is optional and applies to all videos in the batch:

```json
{
  "defaults": {
    "pix_fmt": "yuv420p",
    "test_pattern": "testsrc2",
    "preset": "veryslow",
    "output_dir": "video"
  }
}
```

Defaults can be overridden by individual video configurations.

## Global Bitrate Formula

The `bitrate_formula` at the root level is optional and applies to all videos that don't have their own `bitrate` or `bitrate_formula`:

```json
{
  "bitrate_formula": "width * height * fps * 0.1"
}
```

### Bitrate Formula Syntax

**Variables**:
- `width`: Video width in pixels
- `height`: Video height in pixels
- `fps`: Frames per second

**Operators**: `+`, `-`, `*`, `/`, `**` (exponentiation), parentheses

**Examples**:
```json
"bitrate_formula": "width * height * fps * 0.1"
"bitrate_formula": "width * height * fps * 0.15"
"bitrate_formula": "(width * height * fps) / 1000000 * 8"
```

**Security**: Only arithmetic operations are allowed. Dangerous patterns are rejected.

## Configuration Priority

When merging configurations, the priority order is:

1. **Defaults** (lowest priority)
2. **Video config** (medium priority)
3. **CLI overrides** (highest priority, when using `--config` with CLI args)

## Supported Codecs

- **H.264**: `h264`, `h.264`, `x264`
- **H.265/HEVC**: `h265`, `h.265`, `hevc`, `x265`
- **VP8**: `vp8`
- **VP9**: `vp9`
- **AV1**: `av1`, `aom`
- **MPEG-4**: `mpeg4`, `mpeg-4`

## Examples

### Simple Single Video

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

### Multiple Videos with Defaults

```json
{
  "videos": [
    {
      "resolution": "480p",
      "fps": 30,
      "codec": "h264",
      "duration": 10
    },
    {
      "resolution": "720p",
      "fps": 30,
      "codec": "h264",
      "duration": 10
    },
    {
      "resolution": "1080p",
      "fps": 60,
      "codec": "h265",
      "duration": 10
    }
  ],
  "defaults": {
    "pix_fmt": "yuv420p",
    "test_pattern": "testsrc2"
  }
}
```

### Advanced with Custom Bitrates

```json
{
  "videos": [
    {
      "resolution": "1080p",
      "fps": 30,
      "codec": "h264",
      "duration": 10
    },
    {
      "resolution": "2160p",
      "fps": 30,
      "codec": "vp9",
      "duration": 10,
      "bitrate": "50M"
    },
    {
      "resolution": "4K",
      "fps": 30,
      "codec": "h265",
      "duration": 10,
      "bitrate_formula": "width * height * fps * 0.15"
    }
  ],
  "defaults": {
    "output_dir": "video"
  },
  "bitrate_formula": "width * height * fps * 0.1"
}
```

### Using Explicit Dimensions

```json
{
  "videos": [
    {
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "codec": "h264",
      "duration": 10
    }
  ]
}
```

### YAML Format Example

```yaml
videos:
  - resolution: 1080p
    fps: 30
    codec: h264
    duration: 10
  - resolution: 1080p
    fps: 60
    codec: h265
    duration: 10

defaults:
  pix_fmt: yuv420p
  test_pattern: testsrc2

bitrate_formula: width * height * fps * 0.1
```

## Common Patterns

### Generate All Common Resolutions

```json
{
  "videos": [
    {"resolution": "480p", "fps": 30, "codec": "h264", "duration": 10},
    {"resolution": "720p", "fps": 30, "codec": "h264", "duration": 10},
    {"resolution": "1080p", "fps": 30, "codec": "h264", "duration": 10},
    {"resolution": "1080p", "fps": 60, "codec": "h264", "duration": 10},
    {"resolution": "2160p", "fps": 30, "codec": "h265", "duration": 10},
    {"resolution": "4K", "fps": 30, "codec": "vp9", "duration": 10}
  ],
  "defaults": {
    "output_dir": "video"
  }
}
```

### Multiple Codecs for Same Resolution

```json
{
  "videos": [
    {"resolution": "1080p", "fps": 30, "codec": "h264", "duration": 10},
    {"resolution": "1080p", "fps": 30, "codec": "h265", "duration": 10},
    {"resolution": "1080p", "fps": 30, "codec": "vp9", "duration": 10},
    {"resolution": "1080p", "fps": 30, "codec": "av1", "duration": 10}
  ]
}
```

## Troubleshooting

### "Config file must contain 'videos' key"

Make sure your config file has a `videos` array at the root level, not a plain list.

**Wrong**:
```json
[
  {"resolution": "1080p", "fps": 30, "codec": "h264", "duration": 10}
]
```

**Correct**:
```json
{
  "videos": [
    {"resolution": "1080p", "fps": 30, "codec": "h264", "duration": 10}
  ]
}
```

### Missing Required Fields

Each video must have: resolution (or width+height), fps, codec, and duration.

### Invalid Resolution Format

Use presets (`1080p`, `4K`) or explicit format (`1920x1080`), not both.

## See Also

- Main user guide: `scripts/GUIDE_generate_golden_video.md`
- Example files in this directory: `example_*.json`, `example.yaml`
