# =============================
4) Approve the plan or run automatically:
```bash
gerg -y "compress the Downloads folder into downloads.zip"
```


## Configure (optional)


Create `~/.config/gerg/config.toml`:
```toml
model = "phi3:latest"
ollama_base_url = "http://127.0.0.1:11434"
confirm_by_default = true
history_dir = "~/.local/share/gerg"
```


## Examples


```bash
# Only print commands (never execute)
gerg --print "find the 5 largest files under ~/Downloads"


# Use a different model just for this run
gerg -m llama3:8b "init a git repo, make first commit"


# Work from another directory (without cd'ing first)
gerg --cwd ~/Projects/website "build the site and serve locally"


# Stream model thoughts (justification) if available
gerg --verbose "kill the process listening on port 8080"
```


## Why JSON plans?


The agent prompt asks the model to return a **strict JSON** plan with `explanation`, `commands`, and `require_confirmation`. This keeps execution deterministic and auditable. Plans and run results are stored in `.gerg_history.jsonl` in your working directory (and optionally in `history_dir`).


---


## Safety


- Denylist (e.g., `rm -rf /`, `:(){ :|:& };:`, `mkfs`, `shutdown`, etc.).
- Path confinement: you can require commands to stay under `--cwd`.
- Dry‑run by default; `--yes` to execute.
- `--allow-unsafe` required for commands matching the denylist.


---


## Development


```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest -q
```
