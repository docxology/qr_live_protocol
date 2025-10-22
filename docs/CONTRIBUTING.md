# Contributing to QR Live Protocol

Thank you for your interest in contributing to QRLP! This guide will help you get started with contributing to the project.

## Quick Start

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create** a new branch for your feature/fix
4. **Make** your changes
5. **Test** thoroughly
6. **Submit** a pull request

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Basic understanding of Python and web technologies

### Local Development Environment

```bash
# Clone your fork
git clone https://github.com/your-username/qr_live_protocol.git
cd qr_live_protocol

# Modern setup with uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
uv pip install -e .[dev]

# Alternative: Traditional pip setup
# python3 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt
# pip install -e .[dev]

# Run tests to verify setup
pytest tests/
```

### Project Structure

```
qr_live_protocol/
├── src/                    # Core QRLP source code
│   ├── __init__.py
│   ├── core.py             # Main coordinator (QRLiveProtocol)
│   ├── qr_generator.py     # QR code generation
│   ├── time_provider.py    # Time synchronization
│   ├── blockchain_verifier.py  # Blockchain verification
│   ├── identity_manager.py # Identity management
│   ├── web_server.py       # Web interface
│   ├── cli.py              # Command-line interface
│   └── config.py           # Configuration management
├── templates/              # Web interface templates
├── examples/               # Example scripts and demos
├── tests/                  # Unit and integration tests
├── docs/                   # Documentation
├── main.py                 # Modern demo launcher
├── setup.sh                # Quick setup script with uv
├── pyproject.toml          # Modern Python project configuration
├── setup.py                # Legacy setup (deprecated, use pyproject.toml)
└── requirements.txt        # Legacy dependencies (for compatibility)
```

## Types of Contributions

### 🐛 Bug Reports

When reporting bugs, please include:

- **Clear description** of the issue
- **Steps to reproduce** the problem
- **Expected behavior** vs actual behavior
- **System information** (OS, Python version, QRLP version)
- **Log files** if applicable
- **Screenshots** for UI issues

Use the bug report template:

```markdown
**Bug Description**
A clear description of what the bug is.

**To Reproduce**
1. Start QRLP with command: `...`
2. Navigate to `...`
3. Click on `...`
4. See error

**Expected Behavior**
What you expected to happen.

**System Information**
- OS: [e.g. macOS 12.0, Ubuntu 20.04]
- Python: [e.g. 3.9.7]
- QRLP Version: [e.g. 1.0.0]

**Additional Context**
Any other context about the problem.
```

### ✨ Feature Requests

See our [Feature Requests Guide](FEATURE_REQUESTS.md) for detailed information on requesting new features.

### 📝 Documentation

Documentation improvements are always welcome:

- Fix typos and grammar
- Add examples and use cases
- Improve clarity and organization
- Translate to other languages
- Add diagrams and visual aids

### 🔧 Code Contributions

We welcome code contributions for:

- Bug fixes
- New features
- Performance improvements
- Code quality enhancements
- Test coverage improvements

## Development Guidelines

### Code Style

We use Python's PEP 8 style guide with some modifications:

```python
# Good example
class QRLiveProtocol:
    """Main coordinator for QR Live Protocol operations."""
    
    def __init__(self, config: QRLPConfig = None):
        """Initialize QRLP with optional configuration."""
        self.config = config or QRLPConfig()
        self.running = False
        
    def generate_single_qr(self, user_data: Dict = None) -> Tuple[QRData, bytes]:
        """Generate a single QR code with current verification data.
        
        Args:
            user_data: Optional custom data to include
            
        Returns:
            Tuple of (QRData object, QR image bytes)
        """
        # Implementation here
        pass
```

**Code Style Rules:**
- Use descriptive variable names
- Add type hints for function parameters and returns
- Include docstrings for all public methods
- Keep lines under 88 characters
- Use double quotes for strings
- Add comments for complex logic

### Testing

All contributions must include appropriate tests:

```python
# tests/test_qr_generator.py
import pytest
from src.qr_generator import QRGenerator
from src.config import QRSettings

class TestQRGenerator:
    def setup_method(self):
        """Setup test fixtures."""
        self.settings = QRSettings()
        self.generator = QRGenerator(self.settings)
    
    def test_generate_qr_basic(self):
        """Test basic QR code generation."""
        data = {"test": "data"}
        qr_image = self.generator.generate_qr(data)
        
        assert qr_image is not None
        assert len(qr_image) > 0
        assert isinstance(qr_image, bytes)
    
    def test_generate_qr_error_correction(self):
        """Test QR generation with different error correction levels."""
        data = {"test": "data"}
        
        for level in ["L", "M", "Q", "H"]:
            self.settings.error_correction_level = level
            qr_image = self.generator.generate_qr(data)
            assert qr_image is not None
```

**Testing Guidelines:**
- Write unit tests for all new functions
- Include integration tests for complex features
- Test edge cases and error conditions
- Maintain test coverage above 80%
- Use descriptive test names
- Mock external dependencies

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_qr_generator.py

# Run with coverage
pytest --cov=src tests/

# Run only integration tests
pytest -m integration

# Run tests in parallel
pytest -n auto
```

### Code Quality Tools

Before submitting a PR, run these tools:

```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/

# Security checks
bandit -r src/

# All quality checks
make lint  # If Makefile available
```

## Pull Request Process

### Before Submitting

1. **Sync with upstream** - Ensure your fork is up to date
2. **Create feature branch** - Don't work on main/master
3. **Test thoroughly** - Run all tests and quality checks
4. **Update documentation** - Include relevant docs updates
5. **Check commit messages** - Use descriptive commit messages

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or modifying tests
- `chore:` - Other changes (dependencies, config, etc.)

**Examples:**
```
feat(qr-generator): add support for custom QR styles

- Added new QRStyle enum with predefined styles
- Implemented style application in generate_qr method
- Updated configuration to include style settings

Fixes #123
```

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings introduced
```

### Review Process

1. **Automated checks** - CI/CD pipeline runs tests and quality checks
2. **Code review** - Maintainers review code for quality and design
3. **Feedback incorporation** - Address review comments
4. **Final approval** - Maintainer approves and merges

## Development Workflow

### Branching Strategy

```bash
# Create feature branch
git checkout -b feature/awesome-new-feature

# Work on changes
git add .
git commit -m "feat: add awesome new feature"

# Push to your fork
git push origin feature/awesome-new-feature

# Create PR on GitHub
```

### Working with Issues

1. **Find an issue** - Look for issues labeled `good-first-issue` or `help-wanted`
2. **Comment on issue** - Let others know you're working on it
3. **Create branch** - Use descriptive branch name
4. **Reference issue** - Include issue number in commits/PR

### Development Tips

**Debugging:**
```bash
# Enable debug logging
export QRLP_LOG_LEVEL=DEBUG
python main.py

# Use debugger
import pdb; pdb.set_trace()
```

**Performance Testing:**
```bash
# Profile QR generation
python -m cProfile -o profile.stats main.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats()"
```

**Memory Usage:**
```bash
# Monitor memory usage
pip install memory-profiler
python -m memory_profiler main.py
```

## Community Guidelines

### Code of Conduct

- **Be respectful** - Treat all contributors with respect
- **Be inclusive** - Welcome newcomers and different perspectives
- **Be constructive** - Provide helpful feedback and suggestions
- **Be patient** - Understand that people have different skill levels
- **Be collaborative** - Work together to improve the project

### Communication

- **GitHub Issues** - For bug reports and feature requests
- **GitHub Discussions** - For questions and general discussion
- **Pull Requests** - For code contributions
- **Email** - contact@qrlp.org for private matters

### Recognition

Contributors are recognized in several ways:

- **Contributors file** - Listed in CONTRIBUTORS.md
- **Release notes** - Mentioned in version release notes
- **GitHub profile** - Contributions appear on your GitHub profile
- **Special thanks** - Outstanding contributions get special recognition

## Advanced Contributing

### Architecture Decisions

For significant changes, please:

1. **Create RFC** - Request for Comments for major features
2. **Discuss design** - Get feedback before implementation
3. **Document decisions** - Update architecture documentation
4. **Consider backwards compatibility** - Minimize breaking changes

### Performance Considerations

When contributing performance-related changes:

- **Benchmark before/after** - Measure actual performance impact
- **Consider memory usage** - Monitor memory consumption
- **Test with realistic data** - Use production-like scenarios
- **Document performance characteristics** - Update performance docs

### Security Considerations

For security-related contributions:

- **Follow security best practices** - Use secure coding guidelines
- **Consider attack vectors** - Think about potential security issues
- **Document security implications** - Update security documentation
- **Get security review** - Have security-sensitive changes reviewed

## Release Process

### Version Numbering

We follow Semantic Versioning (SemVer):

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- **MAJOR** - Breaking changes
- **MINOR** - New features (backwards compatible)
- **PATCH** - Bug fixes (backwards compatible)

### Release Timeline

- **Patch releases** - As needed for critical fixes
- **Minor releases** - Monthly or when features are ready
- **Major releases** - Quarterly or when breaking changes accumulate

## Getting Help

### Resources

- **Documentation** - Check docs/ directory
- **Examples** - Look at examples/ directory
- **Tests** - Examine tests/ for usage patterns
- **Issues** - Search existing GitHub issues

### Contact

- **Public discussion** - GitHub Discussions
- **Bug reports** - GitHub Issues
- **Security issues** - security@qrlp.org
- **General questions** - contact@qrlp.org

### Mentorship

New contributors can get help from:

- **Good first issues** - Labeled for beginners
- **Mentorship program** - Pair with experienced contributors
- **Documentation improvements** - Low-risk way to start contributing
- **Code review participation** - Learn by reviewing others' code

---

**Thank you for contributing to QRLP!** 🚀

Your contributions help make QRLP better for everyone. Whether you're fixing a typo, adding a feature, or improving documentation, every contribution is valuable and appreciated. 