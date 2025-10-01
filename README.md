# gerg


**gerg** is a command‑line agent that uses your **local Ollama** model to plan shell commands for a natural‑language task. It shows you the plan as JSON, then (optionally) executes the commands for you.


> Safety-first: by default gerg *asks before running anything*. Use `--yes` to auto‑run, and see `--allow-unsafe` to permit risky commands.


## Install


```bash
pip install . # from a cloned repo
# or once published:
# pip install gerg
```


## Quick start


1) Make sure Ollama is running locally (default `http://127.0.0.1:11434`).
2) Pull a model (for example):
```bash
ollama pull phi3:latest
```
3) Run gerg:
```bash
gerg "list all files in my Downloads directory"
```
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
```
