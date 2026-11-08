"""
Runs every case in tests/cases.json through the real model and saves unedited outputs:
  raw_outputs/<id>.json   full log (raw model replies, case file after each turn, alerts, validator hits)
  raw_outputs/<id>.md     readable transcript
  raw_outputs/summary.csv pass/fail against each case's expectations

Usage:  python run_tests.py                 (uses LLM_PROVIDER / API key from the environment)
        python run_tests.py --only 05_too_old --today 2026-11-08
"""
import argparse
import csv
import json
import os
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent


def load_secrets():
    """Read KEY = "value" lines from .streamlit/secrets.toml so the runner uses the same
    settings as the app. Values already set in the terminal take priority."""
    path = ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', line)
        if m:
            os.environ.setdefault(m.group(1), m.group(2))


load_secrets()   # must run before config.py is imported

from bot import Bot   # noqa: E402
from llm import LLM   # noqa: E402


def run_case(spec, today):
    bot = Bot(LLM(), today=today)
    for turn in spec["turns"]:
        bot.handle(turn)
        if bot.stage in ("stopped", "done"):
            break
    log = bot.export_log()
    final_alerts = {a["code"] for a in (log["turns"][-1]["alerts"] if log["turns"] else [])}
    validator_hits = sum(len(t.get("explain_problems", [])) + len(t.get("facts_problems", []))
                         for t in log["turns"])
    exp = spec["expect"]
    passed = bot.stage == exp["stage"] and set(exp["alerts"]) <= final_alerts
    notice_clean = all(not t.get("notice_problems") for t in log["turns"])
    return bot, log, {
        "id": spec["id"],
        "passed": passed and notice_clean and not any(t.get("llm_error") for t in log["turns"]),
        "expected_stage": exp["stage"], "actual_stage": bot.stage,
        "expected_alerts": " ".join(exp["alerts"]), "actual_alerts": " ".join(sorted(final_alerts)),
        "validator_removed_sentences": validator_hits, "notice_clean": notice_clean,
        "llm_errors": sum(1 for t in log["turns"] if t.get("llm_error")),
        "first_error": next((t["llm_error"] for t in log["turns"] if t.get("llm_error")), ""),
    }


def transcript(spec, log):
    lines = [f"# {spec['id']}", f"_{spec['about']}_", f"Model: {log['model']}  |  Date used: {log['today']}", ""]
    for t in log["turns"]:
        lines += [f"**User:** {t['user']}", "", f"**Bot:** {t['reply']}", ""]
        for a in t["alerts"]:
            lines.append(f"> [{a['level'].upper()}] {a['code']}: {a['message']}")
        for key in ("explain_problems", "facts_problems"):
            for p in t.get(key, []):
                lines.append(f"> VALIDATOR REMOVED: \"{p['sentence']}\" ({'; '.join(p['problems'])})")
        lines.append("\n---\n")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--out", default="raw_outputs")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    print(f"Model: {LLM().name}  |  key found: {bool(LLM().api_key)}  |  date: {today}\n")
    out = ROOT / args.out
    out.mkdir(exist_ok=True)
    cases = json.loads((ROOT / "tests" / "cases.json").read_text(encoding="utf-8"))
    rows = []
    for spec in cases:
        if args.only and spec["id"] not in args.only.split(","):
            continue
        print("running", spec["id"], "...", end=" ", flush=True)
        _, log, row = run_case(spec, today)
        (out / f"{spec['id']}.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / f"{spec['id']}.md").write_text(transcript(spec, log), encoding="utf-8")
        rows.append(row)
        print("PASS" if row["passed"] else "FAIL")
        if row["first_error"]:
            print("   model error:", row["first_error"][:200])
        elif not row["passed"]:
            print(f"   expected {row['expected_stage']} {row['expected_alerts'] or ''}, "
                  f"got {row['actual_stage']} {row['actual_alerts'] or ''}")
    if not rows:
        ids = ", ".join(c["id"] for c in cases)
        print(f"No test case matched --only {args.only!r}.\nValid IDs: {ids}")
        return

    # merge with earlier results so re-running a few cases doesn't erase the others
    summary_path = out / "summary.csv"
    merged = {}
    if summary_path.exists():
        with open(summary_path, newline="", encoding="utf-8") as f:
            merged = {r["id"]: r for r in csv.DictReader(f)}
    merged.update({r["id"]: r for r in rows})
    ordered = [merged[c["id"]] for c in cases if c["id"] in merged]
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(ordered)
    total_passed = sum(str(r["passed"]) == "True" for r in ordered)
    print(f"\nThis run: {sum(r['passed'] for r in rows)}/{len(rows)} passed. "
          f"All cases so far: {total_passed}/{len(ordered)} passed. Outputs in {out}/")


if __name__ == "__main__":
    main()
