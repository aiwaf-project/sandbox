#!/usr/bin/env python
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _list_result_files(directory: Path) -> List[Path]:
    return [p for p in directory.iterdir() if p.is_file() and p.name.startswith("results_") and p.name.endswith(".json")]


def _pick_latest_for_target(directory: Path, prefix: str) -> Optional[Path]:
    candidates = [p for p in _list_result_files(directory) if p.name.startswith(f"results_{prefix}_")]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _expand_arg(arg: str, base_dir: Path) -> List[Path]:
    matches = [Path(p) for p in glob.glob(str(base_dir / arg))]
    return [p for p in matches if p.is_file()]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_attack(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for a in (report.get("attacks") or []):
        attack_type = a.get("attack_type")
        if attack_type:
            out[str(attack_type)] = a
    return out


def _pct(blocked: int, total: int) -> str:
    return f"{(blocked / total * 100.0):.1f}%" if total else "0.0%"


def _target_from_filename(name: str) -> Optional[str]:
    if not (name.startswith("results_") and name.endswith(".json")):
        return None
    core = name[len("results_") : -len(".json")]
    parts = core.split("_")
    if len(parts) < 2:
        return None
    if parts[-1] in {"normal", "attacks", "all"}:
        return "_".join(parts[:-1])
    return parts[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare attack-suite result JSONs (Python)")
    parser.add_argument("files", nargs="*", help="Optional result files or globs")
    parser.add_argument("--json", action="store_true", help="Print JSON summary only")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent

    resolved: List[Path] = []
    for token in args.files:
        if any(ch in token for ch in "*?[]"):
            resolved.extend(_expand_arg(token, base_dir))
        else:
            resolved.append(base_dir / token)
    resolved = [p for p in resolved if p.exists() and p.is_file()]

    files_by_target: Dict[str, Path] = {}
    if resolved:
        for p in resolved:
            target = _target_from_filename(p.name)
            if target and target not in files_by_target:
                files_by_target[target] = p
    else:
        for p in _list_result_files(base_dir):
            target = _target_from_filename(p.name)
            if not target or target in files_by_target:
                continue
            latest = _pick_latest_for_target(base_dir, target)
            if latest:
                files_by_target[target] = latest

    if "direct" not in files_by_target:
        raise SystemExit("Need at least one results_direct_*.json file.")
    if len(files_by_target) < 2:
        raise SystemExit("Need at least one protected target result file in addition to direct.")

    targets = ["direct"] + sorted(t for t in files_by_target if t != "direct")
    reports_by_target = {t: _load_json(files_by_target[t]) for t in targets}
    by_attack = {t: _index_by_attack(reports_by_target[t]) for t in targets}

    attack_types = sorted(set().union(*(set(v.keys()) for v in by_attack.values())))
    rows: List[Dict[str, Any]] = []
    totals = {t: {"blocked": 0, "requests": 0} for t in targets}
    for attack in attack_types:
        row: Dict[str, Any] = {"attack_type": attack}
        for target in targets:
            entry = by_attack[target].get(attack, {})
            row[f"{target}_blocked"] = int(entry.get("blocked") or 0)
            row[f"{target}_requests"] = int(entry.get("requests_sent") or 0)
        rows.append(row)
        for target in targets:
            totals[target]["blocked"] += row[f"{target}_blocked"]
            totals[target]["requests"] += row[f"{target}_requests"]

    summary = {"files": {t: os.path.relpath(str(files_by_target[t]), str(base_dir)) for t in targets}, "rows": rows, "totals": totals}

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    title_cols = ["Attack Type"] + [t.replace("protected_", "").upper() for t in targets]
    print("\n" + " | ".join(f"{c:<16}" for c in title_cols))
    print("-" * (20 * len(title_cols)))
    for row in rows:
        cols = [f"{row['attack_type']:<16}"]
        for target in targets:
            b = row[f"{target}_blocked"]
            r = row[f"{target}_requests"]
            cols.append(f"{b:>3}/{r:<4} {_pct(b, r):>6}")
        print(" | ".join(cols))
    print("-" * (20 * len(title_cols)))
    total_cols = [f"{'TOTAL':<16}"]
    for target in targets:
        b = totals[target]["blocked"]
        r = totals[target]["requests"]
        total_cols.append(f"{b:>3}/{r:<4} {_pct(b, r):>6}")
    print(" | ".join(total_cols))
    print("")


if __name__ == "__main__":
    main()
