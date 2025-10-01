from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

from .config import load_settings
from .agent import request_plan
from .safety import is_risky
from .utils import write_history_line

ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"


def _print_plan(plan) -> None:
    print(f"{ANSI_BOLD}Plan:{ANSI_RESET} {plan.explanation}")
    for i, cmd in enumerate(plan.commands, 1):
        print(f"  {i:>2}. {cmd}")


def execute_commands(commands: List[str], cwd: Path) -> int:
    cur_cwd = cwd

    for i, raw_cmd in enumerate(commands, 1):
        cmd = raw_cmd.strip()

        # Handle 'cd <path>' locally to persist across subsequent commands
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            # Expand ~ and make relative paths relative to current working dir
            new_dir = Path(target).expanduser()
            if not new_dir.is_absolute():
                new_dir = (cur_cwd / new_dir).resolve()

            print(f"\n{ANSI_BOLD}▶ Changing directory {i}/{len(commands)}:{ANSI_RESET} {new_dir}")
            if not new_dir.exists() or not new_dir.is_dir():
                print(f"Directory does not exist: {new_dir}", file=sys.stderr)
                return 1
            cur_cwd = new_dir
            continue

        print(f"\n{ANSI_BOLD}▶ Running {i}/{len(commands)}:{ANSI_RESET} {cmd}")
        proc = subprocess.run(cmd, shell=True, cwd=str(cur_cwd))
        if proc.returncode != 0:
            print(f"Command failed with return code {proc.returncode}", file=sys.stderr)
            return proc.returncode

    return 0



def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="gerg",
        description="CLI agent powered by your local Ollama model",
    )
    parser.add_argument("goal", nargs=argparse.REMAINDER, help="Natural-language goal for the agent")
    parser.add_argument("-y", "--yes", action="store_true", help="Run the planned commands without asking")
    parser.add_argument("--print", dest="print_only", action="store_true", help="Only print the plan (never execute)")
    parser.add_argument("-m", "--model", help="Override model for this run (e.g. llama3:8b)")
    parser.add_argument("--cwd", default=None, help="Run as if started from this directory")
    parser.add_argument("--allow-unsafe", action="store_true", help="Allow commands that match the denylist (be careful)")
    parser.add_argument("--verbose", action="store_true", help="Show extra info about settings and request")

    args = parser.parse_args(argv)

    if not args.goal:
        parser.error('Please provide a goal, e.g. gerg "list all files in my Downloads"')

    goal = " ".join(args.goal).strip()

    settings = load_settings()
    model = args.model or settings.model
    base_url = settings.ollama_base_url

    run_dir = Path(args.cwd).expanduser().resolve() if args.cwd else Path.cwd()

    if args.verbose:
        print(f"Using model={model} base_url={base_url} cwd={run_dir}")

    # Ask the model for a plan
    plan = request_plan(base_url=base_url, model=model, user_goal=goal)

    # Safety checks before printing/confirming
    risky = [c for c in plan.commands if is_risky(c)]
    if risky and not args.allow_unsafe:
        print("\nRefusing potentially unsafe commands:")
        for c in risky:
            print(f"  - {c}")
        print("Re-run with --allow-unsafe if you are absolutely sure.")
        write_history_line(run_dir, {
            "goal": goal,
            "model": model,
            "plan": {
                "explanation": plan.explanation,
                "commands": plan.commands,
                "require_confirmation": plan.require_confirmation,
            },
            "status": "blocked_unsafe",
        })
        return 2

    print()
    _print_plan(plan)

    # Reject plans that contain no actionable commands
    nontrivial = [c for c in plan.commands if c.strip() and not c.strip().lower().startswith("cd ")]
    if not nontrivial:
        print("The plan contains only directory changes or no actionable commands.")
        print('Tip: try rephrasing, e.g., gerg --print "list all PDFs in ~/Downloads"')
        write_history_line(run_dir, {
            "goal": goal,
            "model": model,
            "plan": plan.__dict__,
            "status": "no_actionable_commands",
        })
        return 0


    if args.print_only:
        write_history_line(run_dir, {
            "goal": goal,
            "model": model,
            "plan": plan.__dict__,
            "status": "printed",
        })
        return 0

    # Confirmation logic
    need_confirm = plan.require_confirmation and not args.yes
    if need_confirm:
        ans = input("\nProceed to run these commands? [y/N] ").strip().lower()
        if ans not in {"y", "yes"}:
            print("Aborted.")
            write_history_line(run_dir, {
                "goal": goal,
                "model": model,
                "plan": plan.__dict__,
                "status": "aborted",
            })
            return 0

    rc = execute_commands(plan.commands, cwd=run_dir)

    write_history_line(run_dir, {
        "goal": goal,
        "model": model,
        "plan": plan.__dict__,
        "status": "success" if rc == 0 else "failed",
        "return_code": rc,
    })
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

