# Pytest Configuration Fix

## Issue
Pytest was showing duplicate coverage arguments because:
1. `pytest.ini` had `--cov=src --cov-report=html --cov-report=term-missing` in `addopts`
2. Command line also had `--cov=src --cov-report=html`
3. This caused duplicate arguments error

## Fix Applied
✅ Removed coverage options from `pytest.ini` and `pyproject.toml` `addopts`
✅ Now coverage options must be specified on command line

## Usage

### Run tests without coverage:
```bash
pytest tests/ -v
```

### Run tests with coverage:
```bash
pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
```

### Run specific test file:
```bash
pytest tests/test_mcp_servers/test_user_context_server.py -v
```

## Install pytest-cov if needed:
```bash
pip install pytest-cov
```

Or install all dev dependencies:
```bash
pip install -e ".[dev]"
```

