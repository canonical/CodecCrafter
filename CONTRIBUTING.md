# Contributing to CodecCrafter

Thank you for your interest in contributing to CodecCrafter! This document provides guidelines and instructions for contributing.

## How to Contribute

### Reporting Issues

If you find a bug or have a suggestion for improvement:

1. **Check existing issues** - Search the issue tracker to see if the issue has already been reported
2. **Create a new issue** - Provide a clear title and description
3. **Include details**:
   - Steps to reproduce (for bugs)
   - Expected vs. actual behavior
   - Environment details (OS, Python version, FFmpeg version)
   - Relevant error messages or logs

### Contributing Code

#### Setting Up Development Environment

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/CodecCrafter.git
   cd CodecCrafter
   ```
3. **Install dependencies**:
   ```bash
   uv pip install -r requirements.txt
   # or
   pip install -r requirements.txt
   ```
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

#### Making Changes

1. **Follow code style**:
   - Use Python 3.8+ features
   - Follow PEP 8 style guidelines
   - Use type hints where appropriate
   - Add docstrings to new functions/classes

2. **Test your changes**:
   - Test with different codecs and resolutions
   - Verify reproducibility (same config produces identical output)
   - Test error handling

3. **Update documentation**:
   - Update relevant guides if you add features
   - Add examples if introducing new functionality
   - Update README if needed

#### Submitting Changes

1. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```
   - Write clear, descriptive commit messages
   - Reference issue numbers if applicable (e.g., "Fix #123: ...")

2. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request**:
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template with:
     - Description of changes
     - Related issues
     - Testing performed

## Contribution Guidelines

### Code Contributions

#### Adding a New Codec

1. Create a new handler class in `scripts/generate_golden_video.py`:
   ```python
   class MyCodecHandler(CodecHandler):
       def __init__(self):
           super().__init__("libmycodec", "container")
       
       def get_speed_param(self, preset: str) -> List[str]:
           # Implementation
       
       def get_essential_params(self, gop_size: int) -> List[str]:
           # Implementation
       
       def get_codec_params(self) -> List[str]:
           # Implementation
   ```

2. Register it in `CodecRegistry._register_default_codecs()`

3. Add tests/examples

4. Update documentation

#### Adding New Features

- Keep the extensible architecture in mind
- Maintain backward compatibility when possible
- Add configuration options rather than hardcoding
- Document new features in guides

#### Bug Fixes

- Include a test case that demonstrates the bug
- Ensure the fix doesn't break existing functionality
- Update relevant documentation

### Documentation Contributions

- Fix typos and improve clarity
- Add examples for common use cases
- Improve guides with better explanations
- Translate documentation (if applicable)

### Configuration Examples

- Add example config files for new use cases
- Document edge cases and advanced scenarios
- Provide YAML alternatives to JSON examples

## Code Style

### Python

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters (flexible for readability)
- Use descriptive variable names
- Add docstrings for public functions/classes

### Commit Messages

- Use imperative mood ("Add feature" not "Added feature")
- Keep first line under 72 characters
- Reference issues: "Fix #123: Description"
- Explain "why" in the body if needed

Example:
```
Add support for VP10 codec

Implements VP10Handler with proper reproducibility settings.
Includes tests and documentation updates.

Fixes #456
```

## Testing

Before submitting:

1. **Test locally**:
   ```bash
   # Test single video generation
   python scripts/generate_golden_video.py --resolution 1080p --fps 30 --codec h264 --duration 5
   
   # Test batch generation
   python scripts/generate_golden_video.py --config example_config/example_simple.json
   ```

2. **Verify reproducibility**:
   - Generate the same video twice
   - Compare checksums (should be identical)
   - Test on different machines if possible

3. **Test error handling**:
   - Invalid configs
   - Missing codecs
   - Invalid parameters

## Pull Request Process

1. **Ensure your PR**:
   - Has a clear description
   - References related issues
   - Includes tests/examples
   - Updates documentation if needed
   - Follows code style guidelines

2. **Review process**:
   - Maintainers will review your PR
   - Address any feedback or requested changes
   - PRs require at least one approval before merging

3. **After approval**:
   - Your PR will be merged
   - Thank you for contributing!

## Questions?

- Open an issue for questions about contributing
- Check existing documentation first
- Be respectful and constructive in discussions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License for code, CC BY 4.0 for generated videos).
