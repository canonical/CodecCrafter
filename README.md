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
├── scripts/                    # Video generation scripts
│   ├── generate_golden_video.py    # Main video generation script
│   ├── GUIDE_generate_golden_video.md  # User guide for the script
│   └── config/                  # Config files for GitHub Actions
│       └── .gitkeep            # Placeholder (add your .json/.yaml configs here)
├── example_config/             # Example configuration files
│   ├── GUIDE_config.md         # Guide for writing config files
│   ├── example_simple.json     # Simple single video example
│   ├── example_batch.json      # Multiple videos with defaults
│   ├── example_advanced.json   # Advanced config with bitrate formulas
│   ├── example_av1.json        # AV1-specific examples
│   └── example.yaml            # YAML format example
├── video/                      # Generated golden videos (output directory)
├── requirements.txt            # Python dependencies
├── .github/
│   └── workflows/
│       └── generate-videos.yml # GitHub Actions workflow for auto-generation
└── README.md                   # This file
```

## Quick Start

### Prerequisites

- **Python 3.8+**
- **FFmpeg** with codec support (libx264, libx265, libvpx, libvpx-vp9, libaom-av1)
- **uv** (recommended) or pip for package management

### Installation

#### Using uv (Recommended)

1. Install uv:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Or with pip:

   ```bash
   pip install uv
   ```

2. Install dependencies:

   ```bash
   uv pip install -r requirements.txt
   ```

#### Using pip

```bash
pip install -r requirements.txt
```

### Generate a Single Video

```bash
# Generate a 1080p H.264 video
./scripts/generate_golden_video.py --resolution 1080p --fps 30 --codec h264 --duration 10

# Generate with explicit dimensions
./scripts/generate_golden_video.py --width 1920 --height 1080 --fps 60 --codec h265 --duration 10
```

### Generate Videos from Config File

```bash
# Use an example config
./scripts/generate_golden_video.py --config example_config/example_batch.json

# Use your own config
./scripts/generate_golden_video.py --config scripts/config/my_videos.json --output-dir video
```

## Supported Codecs

- **H.264** (aliases: `h264`, `h.264`, `x264`) → `.mp4`
- **H.265/HEVC** (aliases: `h265`, `h.265`, `hevc`, `x265`) → `.mp4`
- **VP8** → `.webm`
- **VP9** → `.webm`
- **AV1** (aliases: `av1`, `aom`) → `.webm`
- **MPEG-4** (aliases: `mpeg4`, `mpeg-4`) → `.mp4`

## Configuration Files

Configuration files define which videos to generate. They can be written in JSON or YAML format.

### Basic Example

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

### With Defaults and Bitrate Formula

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
      "duration": 10
    }
  ],
  "defaults": {
    "pix_fmt": "yuv420p",
    "test_pattern": "testsrc2",
    "output_dir": "video"
  },
  "bitrate_formula": "width * height * fps * 0.1"
}
```

For detailed configuration documentation, see:

- **[Configuration Guide](example_config/GUIDE_config.md)** - Complete guide for writing config files
- **[Example Configs](example_config/)** - Ready-to-use examples

## GitHub Actions Workflow

This repository includes a GitHub Actions workflow that automatically generates videos when config files are updated.

### How It Works

1. **Place config files** in `scripts/config/` directory (`.json` or `.yaml` format)
2. **Commit and push** the config files to the `main` branch
3. **Workflow triggers** automatically and generates videos
4. **Videos are committed** back to the repository in the `video/` folder

### Manual Trigger

You can also manually trigger the workflow from the GitHub Actions tab:

1. Go to **Actions** -> **Generate Golden Videos**
2. Click **Run workflow**
3. Select branch and click **Run workflow**

### Workflow Features

- Automatically processes all config files in `scripts/config/`
- Only commits videos if they changed (avoids empty commits)
- Supports both JSON and YAML config files
- Skips existing videos by default (configurable)
- Provides summary of generation results

### Example Workflow

```bash
# 1. Create a config file
cat > scripts/config/my_videos.json << EOF
{
  "videos": [
    {"resolution": "1080p", "fps": 30, "codec": "h264", "duration": 10},
    {"resolution": "1080p", "fps": 60, "codec": "h265", "duration": 10}
  ],
  "defaults": {"output_dir": "video"}
}
EOF

# 2. Commit and push
git add scripts/config/my_videos.json
git commit -m "Add video generation config"
git push

# 3. GitHub Actions will automatically generate the videos
```

## Reproducibility

All videos are generated with **maximum reproducibility settings** to ensure bit-exact output:

- Single-threaded encoding (`-threads 1`)
- Fixed GOP structure (2 seconds worth of frames)
- Deterministic codec parameters
- Metadata stripping (`-bitexact`)
- Disabled parallel processing features

This ensures that the same configuration produces identical video files across different machines and runs, making them suitable for:

- Golden file validation
- Regression testing
- Checksum verification
- CI/CD pipelines

## Extending the Script

The script uses an extensible architecture that makes it easy to add new codecs or parameters.

### Adding a New Codec

1. Create a handler class inheriting from `CodecHandler`
2. Implement required methods (`get_encoder()`, `get_flags()`, etc.)
3. Register it in the `CodecRegistry`

See the [User Guide](scripts/GUIDE_generate_golden_video.md#extending-the-script) for detailed instructions.

## Documentation

- **[User Guide](scripts/GUIDE_generate_golden_video.md)** - Complete guide for using the script
- **[Configuration Guide](example_config/GUIDE_config.md)** - How to write config files
- **[Example Configs](example_config/)** - Ready-to-use configuration examples

## Requirements

- Python 3.8+
- FFmpeg with codec support
- PyYAML (for YAML config support)

Install dependencies:

```bash
uv pip install -r requirements.txt
# or
pip install -r requirements.txt
```

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

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- How to report issues
- How to submit code changes
- Code style guidelines
- Adding new codecs or features
- Documentation improvements

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and test them
4. Commit with clear messages (`git commit -m 'Add amazing feature'`)
5. Push to your fork (`git push origin feature/amazing-feature`)
6. Open a Pull Request

For detailed guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).
