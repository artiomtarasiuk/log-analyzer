# Log analyzer

NGINX logs analyzer.
## Setup (optional)

 - Setup python 3.8 venv
 - Install poetry `pip install poetry==1.1.11`
 - Run `poetry install --no-root` to install dependencies (optional)

## Usage

To run:
`python3 log_analyzer.py`

By default it uses config.json located in the root.

To specify your config file add `--config /path/to/file.json`.

Pay attention to the config.json structure.