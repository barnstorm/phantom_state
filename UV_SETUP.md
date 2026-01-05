# Using Phantom State with uv

[uv](https://github.com/astral-sh/uv) is an extremely fast Python package installer and resolver written in Rust. It's 10-100x faster than pip for most operations.

## Why uv?

- **Speed**: Install dependencies in seconds instead of minutes
- **Reliability**: Better dependency resolution
- **Compatibility**: Drop-in replacement for pip
- **Modern**: Built for Python 3.10+

## Installation

### Install uv

```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### Install Phantom State with uv

```bash
# Clone the repository
git clone <repository-url>
cd phantom_state

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Or just the base package
uv pip install -e .

# Or with OpenAI support
uv pip install -e ".[openai]"

# Or everything
uv pip install -e ".[all]"
```

## Running Tests

```bash
# uv automatically uses the local environment
uv run pytest

# Or specific tests
uv run pytest tests/test_two_agents.py -v
```

## Running the MCP Server

### Method 1: Using uv run (Recommended)

This is the cleanest approach - uv handles environment management automatically:

```bash
# Run with uv (automatically creates/manages environment)
uv run python -m phantom_state.mcp
```

### Method 2: Using installed package

```bash
# If installed in your environment
python -m phantom_state.mcp
```

## MCP Client Configuration

### For Claude Desktop (with uv)

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "phantom_state": {
      "command": "uv",
      "args": ["run", "--with", "phantom_state", "python", "-m", "phantom_state.mcp"],
      "env": {
        "PHANTOM_DB_PATH": "narrative.db",
        "PHANTOM_EMBEDDING_BACKEND": "local",
        "PHANTOM_EMBEDDING_MODEL": "all-MiniLM-L6-v2",
        "PHANTOM_VECTOR_DIMENSIONS": "384"
      }
    }
  }
}
```

**How this works:**
- `uv run` creates an isolated environment
- `--with phantom_state` ensures phantom_state is installed
- Automatic dependency management - no manual installation needed!

### For Claude Desktop (traditional)

If you prefer traditional installation:

```json
{
  "mcpServers": {
    "phantom_state": {
      "command": "python",
      "args": ["-m", "phantom_state.mcp"],
      "env": {
        "PHANTOM_DB_PATH": "narrative.db",
        "PHANTOM_EMBEDDING_BACKEND": "local"
      }
    }
  }
}
```

## Development Workflow

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=phantom_state

# Quick test of MCP server
uv run python test_mcp_server.py

# Run example
uv run python examples/basic_dialogue.py
```

## Performance Comparison

Typical installation times on a clean environment:

| Method | Time |
|--------|------|
| `pip install -e .` | ~2-3 minutes |
| `uv pip install -e .` | ~15-30 seconds |

For the full `.[all]` installation:

| Method | Time |
|--------|------|
| `pip install -e ".[all]"` | ~5-8 minutes |
| `uv pip install -e ".[all]"` | ~30-60 seconds |

## Tips & Tricks

### 1. Quick Dependency Updates

```bash
# Update all dependencies
uv pip install -e ".[all]" --upgrade

# Much faster than pip!
```

### 2. Using uv run for Scripts

```bash
# Run any Python script with dependencies managed by uv
uv run python my_script.py

# uv handles the environment automatically
```

### 3. Creating Test Environments

```bash
# Create isolated test environment
uv venv test-env
source test-env/bin/activate  # or test-env\Scripts\activate on Windows
uv pip install -e ".[dev]"
```

### 4. Checking Installed Packages

```bash
# List installed packages
uv pip list

# Show dependency tree
uv pip show phantom_state
```

## Troubleshooting

### "uv: command not found"

Make sure uv is in your PATH. After installation, restart your terminal or run:

```bash
# On Unix
source ~/.bashrc  # or ~/.zshrc

# On Windows
# Restart PowerShell/Command Prompt
```

### Package not found when using uv run

If `uv run --with phantom_state` fails, try installing locally first:

```bash
cd phantom_state
uv pip install -e .
```

### Slow first run

The first time you use uv, it may need to:
- Download Python versions
- Build package metadata cache
- Compile Rust components (for some dependencies)

Subsequent runs will be much faster due to caching.

## Migration from pip

Already using pip? Here's how to migrate:

```bash
# 1. Uninstall existing installation (optional)
pip uninstall phantom_state

# 2. Install uv
pip install uv

# 3. Use uv for everything going forward
uv pip install -e ".[dev]"

# All pip commands work with uv:
# pip install -> uv pip install
# pip list -> uv pip list
# pip show -> uv pip show
```

## Additional Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [uv vs pip Benchmarks](https://github.com/astral-sh/uv#benchmarks)
- [Python Packaging with uv](https://github.com/astral-sh/uv/blob/main/PACKAGING.md)
