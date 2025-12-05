# effective-mobile-ui-tests

## Quick start

1. Create venv and activate:
   - `python -m venv .venv && source .venv/bin/activate` (Linux/macOS)
   - `python -m venv .venv && .\\.venv\\Scripts\\activate` (Windows)
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Install Playwright browsers:
   - `playwright install`
4. Run tests:
   - `pytest -q`

## Options
- Override base URL: `pytest -q --base-url=https://example.com`
- Run headed: `pytest -q --headless=0`

## Docker
- Build: `docker build -t em-tests .`
- Run: `docker run --rm em-tests`
