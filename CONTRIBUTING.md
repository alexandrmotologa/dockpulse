# Contributing to DockPulse

Thank you for your interest in contributing to DockPulse.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/alexandrmotologa/dockpulse.git
   cd dockpulse
   ```

2. Install dependencies with `uv`:
   ```bash
   uv sync --all-extras --dev
   ```

3. Activate the virtual environment:
   - On Windows: `.venv\Scripts\activate`
   - On Linux/macOS: `source .venv/bin/activate`

## Testing and Quality Checks

Run the test suite before submitting changes:

```bash
uv run pytest -v tests/
```

Run code quality and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

To automatically format files:

```bash
uv run ruff format .
```

## Pull Request Guidelines

- Keep pull requests focused on a single feature or fix.
- Add unit tests for new logic, especially socket handling, model parsing, and stats calculations.
- Follow conventional commit style: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
