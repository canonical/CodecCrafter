# CodecCrafter

A collection of consistently generated test videos for a range of formats, resolutions, and codecs. This repository provides a reliable asset suite for testing video players, streaming servers, transcoding pipelines, and decoder performance.

## Repository Purpose

CodecCrafter generates **reproducible golden video samples** with configurable parameters. All videos are generated with maximum reproducibility settings to ensure bit-exact output across different machines and runs, making them ideal for:

- **Testing video players** and decoders
- **Validating streaming servers** and transcoding pipelines
- **Performance benchmarking** of video codecs
- **Regression testing** with consistent reference videos
- **CI/CD pipelines** requiring deterministic video assets

## Repository Structure

```text
CodecCrafter/
├── scripts/
│   ├── generate_golden_video.py    # Video generation script
│   └── config/
│       └── codecs.yaml             # Codec definitions (encoder, container, flags)
├── golden_sample_yaml_config/      # Production configs; CI generates video/ from these
├── example_config/
│   ├── GUIDE_config.md             # Config file schema reference
│   ├── example.yaml                # YAML example
│   └── example_simple.json         # JSON example
├── video/                          # Generated golden videos (output directory)
├── requirements.txt                # Python dependencies
└── .github/workflows/
    └── generate-videos.yml         # CI: validate on PRs, generate on main
```

## Quick Start

### Prerequisites

- **Python 3.8+**
- **FFmpeg** with codec support (libx264, libx265, libvpx, libvpx-vp9, libaom-av1)

### Installation

```bash
pip install -r requirements.txt
```

### Generate a Single Video

```bash
# 1080p H.264 test pattern
./scripts/generate_golden_video.py test_pattern \
  --resolution 1080p --fps 30 --codec h264 --duration 10

# AV sync test video (white flash + beep every second)
./scripts/generate_golden_video.py av_sync \
  --resolution 1080p --fps 30 --codec h264 --duration 10

# Explicit dimensions
./scripts/generate_golden_video.py test_pattern \
  --width 1920 --height 1080 --fps 60 --codec h265 --duration 10
```

### Generate Videos from a Config File

```bash
./scripts/generate_golden_video.py batch \
  --config golden_sample_yaml_config/golden_sample_video_testset.yaml \
  --output-dir video

# Validate a config without encoding anything
./scripts/generate_golden_video.py validate \
  --config golden_sample_yaml_config/golden_sample_video_testset.yaml
```

Config files are JSON or YAML; see the
**[config schema reference](example_config/GUIDE_config.md)**.

## Supported Codecs

Codecs are defined in `scripts/config/codecs.yaml` — **adding or tuning a
codec is a config edit, not a code change** (encoder, container, and the
determinism flags below).

- **H.264** (aliases: `h264`, `h.264`, `x264`) → `.mp4`
- **H.265/HEVC** (aliases: `h265`, `h.265`, `hevc`, `x265`) → `.mp4`
- **VP8** → `.webm`
- **VP9** → `.webm`
- **AV1** (aliases: `av1`, `aom`) → `.webm`
- **MPEG-4** (aliases: `mpeg4`, `mpeg-4`) → `.mp4`

## GitHub Actions Workflow

`generate-videos.yml` drives the repository:

- **Pull requests** touching `scripts/`, `golden_sample_yaml_config/`, or the
  workflow run a **smoke job**: every golden config is validated and one tiny
  video per scenario is encoded. No videos are committed.
- **Pushes to main** (and manual runs) enumerate every video in every config
  in `golden_sample_yaml_config/` into a **job matrix**, encode them in
  parallel on separate runners, then a final job collects the results and
  pushes a single commit to `video/`. Existing videos are skipped, so runs
  are incremental.
- **Manual runs** (Actions → Generate Golden Videos → Run workflow) accept a
  **force_regenerate** flag that re-encodes everything, still in parallel.

## Reproducibility

All videos are generated with **maximum reproducibility settings** for
bit-exact output across machines and runs:

- Single-threaded encoding (`-threads 1`)
- Fixed GOP structure: `-g` and `-keyint_min` locked to `fps * 2`
- Metadata stripping (`-bitexact -fflags +bitexact -map_metadata -1`)
- Scene-change detection disabled for x264/x265 (`-sc_threshold 0`)
- Parallel processing disabled per codec:

| Codec | Speed parameter | Determinism flags |
|---|---|---|
| H.264 (libx264) | `-preset veryslow` | `deterministic=1:no-mbtree=1:no-mixed-refs=1` |
| H.265 (libx265) | `-preset veryslow` | `deterministic=1:no-open-gop=1:no-wpp=1:no-pmode=1:no-pme=1` |
| VP8 (libvpx) | `-cpu-used 0` | — |
| VP9 (libvpx-vp9) | `-cpu-used 0` | `-tile-columns 0 -tile-rows 0 -row-mt 0` |
| AV1 (libaom-av1) | `-cpu-used 0` | — |
| MPEG-4 (mpeg4) | — | — |

The x265 flags disable wavefront/parallel mode decision/parallel motion
estimation; the VP9 flags disable tiling and row multithreading — these are
the main sources of non-deterministic output.

## Documentation

- **[Config schema reference](example_config/GUIDE_config.md)** — how to write config files
- **[Example configs](example_config/)** — ready-to-use examples

## License

This repository uses a dual-license approach:

- **Source Code**: The Python scripts, configuration files, and workflows are licensed under the [MIT License](LICENSE). This allows you to use, modify, and distribute the code with minimal restrictions.

- **Media Assets**: The generated video files in the `video/` directory are licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). This means you can:
  - **Share** - Copy and redistribute the videos
  - **Adapt** - Use the videos for any purpose, including commercially
  - **Attribute** - You must give appropriate credit when using the videos

### Why Dual License?

- **MIT for code**: Allows maximum flexibility for developers to use and modify the generation scripts
- **CC BY 4.0 for videos**: Ensures attribution while allowing free use of the generated test videos for testing, benchmarking, and development purposes

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and test them
4. Commit with clear messages (`git commit -m 'Add amazing feature'`)
5. Push to your fork (`git push origin feature/amazing-feature`)
6. Open a Pull Request
