**gerg** is a command‑line agent that uses your local Ollama model to plan shell commands for a natural‑language task. It can either output the command to help, or execute it for you.


> Safety-first: by default gerg *asks before running anything*. Use `--yes` to auto‑run, and see `--allow-unsafe` to permit risky commands.


## Install


```bash
pip install gerg
```


## Quick start


1) Make sure Ollama is running locally (default `http://127.0.0.1:11434`).
2) Run gerg:
```bash
gerg "list all files in my Downloads directory"
```
3) Approve the plan or run automatically:
```bash
gerg -y "compress the Downloads folder into downloads.zip"
```
4) Need multi-step planning and commands. Enable the --think flag for Chain of Thought planning and execution.

## Examples


```bash
# Only print commands (never execute)
gerg --print "find the 5 largest files under ~/Downloads"


# Use a different model just for this run
gerg -m llama3:8b "init a git repo, make first commit"


# Work from another directory (without cd'ing first)
gerg --cwd ~/Projects/website "build the site and serve locally"

gerg --think "create a .txt file in my Documents folder with a simple rhyme"
```
