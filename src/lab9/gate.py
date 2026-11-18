"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    man = pr.get("manifest") or {}

    # 1. NaN / inf metric values: `nan < min` is False, so a naive threshold check passes them
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (not a finite number)")

    # 2. row count must equal items x seeds of the manifest (dropped rows)
    want = int(man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want}")
    # ... and every (item, seed) exactly once (a duplicate can hide a dropped row from the count)
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dups = sorted({k for k in keys if keys.count(k) > 1}, key=str)
    if dups:
        problems.append(f"{len(dups)} duplicated (item, seed) row(s), e.g. {dups[0]}")

    # 3. same (item, seed) set and same seed list as the baseline (cherry-picked seeds / items)
    base_rows = base.get("rows") or []
    pr_set, base_set = set(keys), {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if pr_set != base_set:
        problems.append(f"(item, seed) set differs from the baseline: {len(base_set - pr_set)} missing, "
                        f"{len(pr_set - base_set)} extra")
    if sorted(man.get("seeds") or []) != sorted((base.get("manifest") or {}).get("seeds") or []):
        problems.append(f"seeds {man.get('seeds')} differ from the baseline's {(base.get('manifest') or {}).get('seeds')}")

    # 4. crashed graders: reported failures, or a graded metric that is None on a row
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for m in graded:
        missing = sum(1 for r in rows if r.get(m) is None)
        if missing:
            problems.append(f"{missing} row(s) with no value for graded metric {m}")

    # 5. reported metrics must be what the rows actually aggregate to (hand-edited / stale metrics)
    row_metrics = [m for m in graded if rows and all(m in r for r in rows)]
    if rows and not problems:
        has_cost = all("cost" in r for r in rows)
        recomputed = aggregate([r if has_cost else {**r, "cost": 0.0} for r in rows], row_metrics,
                               k_values=spec.get("pass_k", []))
        reported = pr.get("metrics") or {}
        # compare only what the report states; a metric left out entirely is MISSING in check()
        for k, v in recomputed.items():
            if k not in reported or (k == "cost_per_success" and not has_cost):
                continue
            got = reported[k]
            same = (got is None and v is None) or (
                isinstance(got, (int, float)) and isinstance(v, (int, float)) and abs(got - v) <= 1e-6)
            if not same:
                problems.append(f"metric {k} reported {got} but the rows give {v}")

    # 6. ratchet: on the same eval-set version thresholds may only get stricter
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(base_spec, spec)

    # 7. slice tags per item must match the baseline's (relabelling an item out of a slice)
    tags = lambda rs: {r.get("item_id"): sorted(r.get("slices") or []) for r in rs}
    pr_tags, base_tags = tags(rows), tags(base_rows)
    moved = sorted(i for i in pr_tags.keys() & base_tags.keys() if pr_tags[i] != base_tags[i])
    if moved:
        problems.append(f"slice tags differ from the baseline on {len(moved)} item(s), e.g. {moved[0]}: "
                        f"{base_tags[moved[0]]} -> {pr_tags[moved[0]]}")
    return problems


def _looser(old: dict, new: dict, what: str) -> list[str]:
    """Threshold `new` may not be looser than `old`. Works for a metric threshold or a slice entry."""
    out = []
    if "max" in old and ("max" not in new or new["max"] > old["max"]):
        out.append(f"{what}: max {old['max']} -> {new.get('max', 'removed')}")
    if "min" in old and ("min" not in new or new["min"] < old["min"]):
        out.append(f"{what}: min {old['min']} -> {new.get('min', 'removed')}")
    if "max_increase" in old and ("max_increase" not in new or new["max_increase"] > old["max_increase"]):
        out.append(f"{what}: max_increase {old['max_increase']} -> {new.get('max_increase', 'removed')}")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        out.append(f"{what}: no_significant_drop removed")
    return out


def _ratchet(base_spec: dict, spec: dict) -> list[str]:
    out = []
    new_metrics = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        n = new_metrics.get(m["id"])
        if n is None:
            out.append(f"RATCHET metric {m['id']} removed")
            continue
        if m.get("blocking") and not n.get("blocking"):
            out.append(f"RATCHET metric {m['id']} no longer blocking")
        out += [f"RATCHET {p}" for p in _looser(m.get("threshold") or {}, n.get("threshold") or {}, m["id"])]
    new_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        sid = f"slice:{s['name']}/{s['metric']}"
        n = new_slices.get((s["name"], s["metric"]))
        if n is None:
            out.append(f"RATCHET {sid} removed")
            continue
        if s.get("blocking") and not n.get("blocking"):
            out.append(f"RATCHET {sid} no longer blocking")
        out += [f"RATCHET {p}" for p in _looser(s, n, sid)]
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        # 1. per-item values (mean over seeds), only items tagged with this slice
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        verdict, note, value = "ok", "", None
        if not a:
            # no PR row carries this slice: items were dropped or relabelled out of it -> never a silent pass
            verdict = "missing"
        else:
            # 2. slice value and 3. floor
            value = round(sum(a.values()) / len(a), 4)
            if "min" in sl and value < sl["min"]:
                verdict = "fail"
            # 4. paired bootstrap over the slice's items present in both reports
            if sl.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] n={len(keys)}"
                    if hi < 0:
                        verdict = "fail"
        # 5. blocking
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<32} {value!s:<8} {json.dumps(th):<40} {note:<34} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
