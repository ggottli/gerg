from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional

from .config import load_settings
from .agent import request_plan, request_next_action
from .safety import is_risky
from .utils import write_history_line

ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"


def _print_plan(plan) -> None:
    print(f"{ANSI_BOLD}Plan:{ANSI_RESET} {plan.explanation}")
    for i, cmd in enumerate(plan.commands, 1):
        print(f"  {i:>2}. {cmd}")


def _read_rag_context(rag_dir: Optional[str], max_chars: int = 20000) -> Optional[str]:
    if not rag_dir:
        return None
    base = Path(rag_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        return None

    exts = {".md", ".txt", ".log", ".json", ".cfg", ".ini", ".toml", ".yml", ".yaml"}
    chunks: List[str] = []
    total = 0

    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            header = f"\n# File: {p.relative_to(base)}\n"
            piece = header + text[: max(0, max_chars - len(header))]
            if total + len(piece) > max_chars:
                piece = piece[: max_chars - total]
            chunks.append(piece)
            total += len(piece)
            if total >= max_chars:
                break

    return "".join(chunks) if chunks else None


def _persisting_execute(commands: List[str], cwd: Path) -> int:
    """
    Execute a list of shell commands, persisting 'cd' across subsequent commands.
    Captures exit codes but streams output directly to the terminal.
    """
    cur_cwd = cwd

    for i, raw_cmd in enumerate(commands, 1):
        cmd = raw_cmd.strip()

        # Handle 'cd' locally so it persists
        if cmd.lower().startswith("cd "):
            target = cmd[3:].strip()
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


def _execute_one_capture(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    """
    Execute a single command and capture stdout/stderr so we can feed observations
    back to the model. Persists cd by returning updated cwd if needed.
    """
    if cmd.lower().startswith("cd "):
        target = cmd[3:].strip()
        new_dir = Path(target).expanduser()
        if not new_dir.is_absolute():
            new_dir = (cwd / new_dir).resolve()
        if not new_dir.exists() or not new_dir.is_dir():
            # Simulate a failing process for invalid cd
            cp = subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr=f"Directory not found: {new_dir}\n")
            return cp
        # Fake a successful "cd" with a message in stdout so the model can observe
        cp = subprocess.CompletedProcess(args=cmd, returncode=0, stdout=f"(cd) now at: {new_dir}\n", stderr="")
        # Patch attribute for caller to pick up new cwd
        cp.new_cwd = new_dir  # type: ignore[attr-defined]
        return cp

    # Normal command
    cp = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True)
    return cp


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="gerg",
        description="CLI agent powered by your local Ollama model",
    )
    parser.add_argument("goal", nargs=argparse.REMAINDER, help="Natural-language goal for the agent")
    parser.add_argument("-y", "--yes", action="store_true", help="Run commands without asking")
    parser.add_argument("--print", dest="print_only", action="store_true", help="Only print the plan (never execute)")
    parser.add_argument("-m", "--model", help="Override model for this run (e.g. llama3:8b)")
    parser.add_argument("--cwd", default=None, help="Run as if started from this directory")
    parser.add_argument("--allow-unsafe", action="store_true", help="Allow commands that match the denylist (be careful)")
    parser.add_argument("--verbose", action="store_true", help="Show extra info about settings and request")

    # Thinking / RAG mode
    parser.add_argument("--think", action="store_true", help="Enable reason-act-observe loop (multi-step)")
    parser.add_argument("--max-steps", type=int, default=8, help="Max steps for --think mode (default: 8)")
    parser.add_argument("--rag-dir", type=str, default=None, help="Optional directory of text files to provide as RAG context")

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

    # ---- THINK MODE ----
    if args.think:
        rag = _read_rag_context(args.rag_dir)
        conversation: List[Dict[str, str]] = [{"role": "user", "content": goal}]
        cur_cwd = run_dir
        history = {
            "mode": "think",
            "goal": goal,
            "model": model,
            "status": "started",
            "steps": [],
        }

        # Per-run safety and confirmation:
        confirmed = args.yes  # if -y, skip per-step prompts

        for step in range(1, max(1, args.max_steps) + 1):
            nxt = request_next_action(
                base_url=base_url,
                model=model,
                user_goal=goal,
                conversation=conversation,
                rag_context=rag,
            )

            # Safety block
            risky = is_risky(nxt.command)
            if risky and not args.allow_unsafe:
                print("\nRefusing potentially unsafe command:")
                print(f"  - {nxt.command}")
                print("Re-run with --allow-unsafe if you are absolutely sure.")
                history["status"] = "blocked_unsafe"
                write_history_line(run_dir, history)
                return 2

            print(f"\n{ANSI_BOLD}Step {step}:{ANSI_RESET} {nxt.explanation}")
            print(f"{ANSI_DIM}Command:{ANSI_RESET} {nxt.command}")

            # Confirm per step unless already confirmed
            if (nxt.require_confirmation or not confirmed) and not args.yes:
                ans = input("Proceed? [y/N] ").strip().lower()
                if ans not in {"y", "yes"}:
                    print("Aborted.")
                    history["status"] = "aborted"
                    write_history_line(run_dir, history)
                    return 0
                confirmed = True  # confirm once and continue silently

            cp = _execute_one_capture(nxt.command, cur_cwd)
            out = (cp.stdout or "")
            err = (cp.stderr or "")
            code = cp.returncode

            # Update cwd if a cd succeeded
            if hasattr(cp, "new_cwd") and cp.returncode == 0:  # type: ignore[attr-defined]
                cur_cwd = getattr(cp, "new_cwd")  # type: ignore[attr-defined]

            # Show output to user (trim long)
            show_out = out if len(out) < 1200 else out[:1200] + "\n...[truncated]..."
            show_err = err if len(err) < 800 else err[:800] + "\n...[truncated]..."
            if show_out.strip():
                print(f"{ANSI_DIM}stdout:{ANSI_RESET}\n{show_out}", end="" if show_out.endswith("\n") else "\n")
            if show_err.strip():
                print(f"{ANSI_DIM}stderr:{ANSI_RESET}\n{show_err}", end="" if show_err.endswith("\n") else "\n")
            print(f"{ANSI_DIM}exit code:{ANSI_RESET} {code}")

            # Append to convo as observation
            conversation.append({"role": "assistant", "content": f"Executed: {nxt.command}\nexit_code={code}"})
            observation = f"OBSERVATION:\nCWD: {cur_cwd}\nEXIT_CODE: {code}\nSTDOUT:\n{out[-4000:]}\nSTDERR:\n{err[-2000:]}"
            conversation.append({"role": "user", "content": observation})

            # Log step
            history["steps"].append({
                "step": step,
                "explanation": nxt.explanation,
                "command": nxt.command,
                "cwd": str(cur_cwd),
                "exit_code": code,
                "stdout_tail": out[-1000:],
                "stderr_tail": err[-800:],
            })

            if nxt.done:
                print(f"\n{ANSI_BOLD}Done.{ANSI_RESET}")
                history["status"] = "success" if code == 0 else "done_with_errors"
                write_history_line(run_dir, history)
                return 0 if code == 0 else code

        print(f"\nReached max steps ({args.max_steps}) without done=true.")
        history["status"] = "max_steps_reached"
        write_history_line(run_dir, history)
        return 0

    # ---- STANDARD (single-plan) MODE ----
    plan = request_plan(base_url=base_url, model=model, user_goal=goal)

    # Safety checks before printing/confirming
    risky_cmds = [c for c in plan.commands if is_risky(c)]
    if risky_cmds and not args.allow_unsafe:
        print("\nRefusing potentially unsafe commands:")
        for c in risky_cmds:
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

    # Reject plans that contain only cd/no-op
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

    rc = _persisting_execute(plan.commands, cwd=run_dir)

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
