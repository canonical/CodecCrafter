# Config File Schema

Batch config files for `scripts/generate_golden_video.py batch`. JSON or
YAML (`.json`, `.yaml`, `.yml`) — same schema, pick either.

## Top-level keys

| Key | Type | Required | Meaning |
|---|---|---|---|
| `videos` | list of video objects | yes (non-empty) | One entry per output video |
| `defaults` | object | no | Values applied to every video unless the video overrides them |
| `bitrate_formula` | string | no | Fallback bitrate formula for videos with no `bitrate`/`bitrate_formula` of their own |

Priority: video entry > `defaults` > built-in default.

## Video object keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `resolution` | string | — | Preset (`480p`, `720p`, `1080p`, `2160p`/`UHD`, `4K`, `8K`) or explicit `1920x1080` / `1920:1080`. Required unless `width`+`height` given |
| `width`, `height` | int | — | Explicit dimensions; alternative to `resolution` |
| `fps` | int | required | Frames per second |
| `codec` | string | required | See codec table below |
| `duration` | float | required | Seconds (av_sync: >= 0.1) |
| `bitrate` | string | computed | e.g. `"40M"`, `"5000k"`; wins over any formula |
| `bitrate_formula` | string | global formula, else `width * height * fps * 0.1` | Arithmetic over `width`, `height`, `fps` only |
| `pix_fmt` | string | `yuv420p` | FFmpeg pixel format |
| `preset` | string | `veryslow` | FFmpeg speed preset |
| `output_dir` | string | batch `--output-dir` | Where the file lands (CLI `--output-dir` overrides `defaults.output_dir`) |
| `output_filename` | string | `{height}p_{fps}fps_{codec}[_avsync].{ext}` | Custom filename |
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
  - resolution: 1080p
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
  output_dir: video

bitrate_formula: width * height * fps * 0.1
```

Same structure in JSON: see `example_simple.json`. Production configs live
in `golden_sample_yaml_config/`.
