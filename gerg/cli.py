# =============================
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


if args.print_only:
write_history_line(run_dir, {
"goal": goal,
"model": model,
"plan": plan.__dict__,
"status": "printed",
})
return 0


need_confirm = plan.require_confirmation or (settings.confirm_by_default and not args.yes)
if need_confirm and not args.yes:
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




if __name__ == "__main__": # pragma: no cover
raise SystemExit(main())
