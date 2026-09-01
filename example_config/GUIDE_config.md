# Config File Schema

Batch config files for `scripts/generate_golden_video.py batch`. JSON or
YAML (`.json`, `.yaml`, `.yml`) — same schema, pick either.

A machine-readable JSON Schema lives at the repo root as
`config.schema.json` (and `config.schema.yaml`), generated from the
script's models by `generate_golden_video.py schema` and kept in sync by
CI. For editor autocomplete and inline docs, add to a JSON config
`"$schema": "../config.schema.json"`, or to a YAML config the first line
`# yaml-language-server: $schema=../config.schema.json`.

## Top-level keys

| Key | Type | Required | Meaning |
|---|---|---|---|
| `videos` | list of video objects | yes (non-empty) | One entry per output video |
| `defaults` | object | no | Values applied to every video unless the video overrides them |
| `bits_per_pixel` | float | no | Fallback for videos with no `bitrate`/`bits_per_pixel` of their own (default `0.1`) |

Priority: video entry > `defaults` > built-in default.

## Video object keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `resolution` | string | — | Explicit `WIDTHxHEIGHT` (`1920x1080`, also `1920:1080`). Required unless `width`+`height` given |
| `width`, `height` | int | — | Explicit dimensions; alternative to `resolution` |
| `fps` | int | required | Frames per second |
| `codec` | string | required | See codec table below |
| `duration` | float | required | Seconds (av_sync: >= 0.1) |
| `bitrate` | string | computed | e.g. `"40M"`, `"5000k"`; wins over `bits_per_pixel` |
| `bits_per_pixel` | float | top-level value, else `0.1` | Bitrate = `width * height * fps * bits_per_pixel` |
| `pix_fmt` | string | `yuv420p` | FFmpeg pixel format |
| `preset` | string | `veryslow` | FFmpeg speed preset |
| `output_dir` | string | batch `--output-dir` | Per-video override for where the file lands. A defaults-level `output_dir` never takes effect in batch mode — the required `--output-dir` flag always replaces it |
| `output_filename` | string | `{width}x{height}_{fps}fps_{codec}[_avsync].{ext}` | Custom filename |
| `skip_existing` | bool | `true` | Skip generation when the output file exists |
| `extra_params` | list of strings | `[]` | Extra FFmpeg args appended to the command |

## Scenarios

`defaults.scenario` selects the generator for the whole file (one scenario
per config file; default `test_pattern`):

- `test_pattern` — lavfi test source. Extra key: `test_pattern` (default
  `testsrc2`). Must NOT set `audio_frequency`/`beep_duration`.
- `av_sync` — black frame with a white flash + beep every second. Extra
  keys: `audio_frequency` (Hz, default `1000`), `beep_duration` (s, default
  `0.1`). Must NOT set `test_pattern`.

## Codecs

Defined in `scripts/config/codecs.yaml` (encoder, container, and
reproducibility flags per codec — edit that file to add or tune codecs):

| Name (aliases) | Encoder | Container |
|---|---|---|
| `h264` (`h.264`, `x264`) | libx264 | mp4 |
| `h265` (`h.265`, `hevc`, `x265`) | libx265 | mp4 |
| `vp8` | libvpx | webm |
| `vp9` | libvpx-vp9 | webm |
| `av1` (`aom`) | libaom-av1 | webm |
| `mpeg4` (`mpeg-4`) | mpeg4 | mp4 |

## Example

```yaml
videos:
  - resolution: 1920x1080
    fps: 30
    codec: h264
    duration: 10
  - width: 3840        # explicit dimensions instead of a preset
    height: 2160
    fps: 60
    codec: vp9
    duration: 10
    bitrate: 50M       # overrides the formula for this video only

defaults:
  scenario: test_pattern   # or av_sync (then audio_frequency/beep_duration apply)
  preset: veryslow

bits_per_pixel: 0.1        # optional; this is the default
```

Same structure in JSON: see `example_simple.json`. Production configs live
in `golden_sample_yaml_config/`.

Check a config without encoding anything:

```bash
python scripts/generate_golden_video.py validate --config my_config.yaml
```
