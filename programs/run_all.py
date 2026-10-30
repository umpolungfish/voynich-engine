#!/usr/bin/env python3
"""
Master Analysis Runner — runs all Voynich Engine analysis programs
and produces a consolidated report.

Usage:
    python programs/run_all.py data/LSI_ivtff_0d.txt [--steps 50000] [--seed 42]
"""

from __future__ import annotations
import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DEFAULT = REPO_ROOT / "data" / "LSI_ivtff_0d.txt"

PROGRAMS = [
    {
        "name": "Bootstrap Cycle Explorer",
        "script": "programs/bootstrap_explorer.py",
        "args": ["--max-mismatches", "2"],
        "description": "Finds Frobenius cycles, spectral gap, transition matrix",
        "accepts_steps": False,
        "accepts_seed": False,
    },
    {
        "name": "Folio Topology Comparator",
        "script": "programs/folio_comparator.py",
        "args": ["--top-n", "10"],
        "description": "Per-folio structural fingerprints, JS divergence between sections",
        "accepts_steps": False,
        "accepts_seed": False,
    },
    {
        "name": "Synthetic EVA Comparator",
        "script": "programs/synthetic_comparator.py",
        "args": [],
        "description": "Zero-entropy test, synthetic vs real engine behavior",
        "accepts_steps": True,
        "accepts_seed": True,
    },
    {
        "name": "Folio Mutation Scanner",
        "script": "programs/mutation_scanner.py",
        "args": [],
        "description": "Glyph knockout, mutation rate scan, section fragility",
        "accepts_steps": True,
        "accepts_seed": True,
    },
    {
        "name": "Paradox Injection Analyzer",
        "script": "programs/paradox_injector.py",
        "args": [],
        "description": "Dialetheic stress testing, section paradox susceptibility",
        "accepts_steps": True,
        "accepts_seed": False,
    },
    {
        "name": "Register Lifecycle Tracker",
        "script": "programs/register_lifecycle.py",
        "args": ["--sample", "2000"],
        "description": "Individual register birth→fixation traces, survival curves",
        "accepts_steps": True,
        "accepts_seed": False,
    },
]


def run_program(prog: dict, data_path: str, steps: int, seed: int, steps_reduced: int) -> tuple[bool, float]:
    """Run a program and return (success, elapsed_seconds)."""
    cmd = [sys.executable, prog["script"], data_path]

    extra_args = list(prog["args"])
    if prog.get("accepts_steps") and "--steps" not in " ".join(prog["args"]):
        extra_args.extend(["--steps", str(steps_reduced if "mutation" in prog["script"] else steps)])
    if prog.get("accepts_seed") and "--seed" not in " ".join(prog["args"]):
        extra_args.extend(["--seed", str(seed)])

    cmd.extend(extra_args)

    print(f"\n{'='*80}")
    print(f"Running: {prog['name']}")
    print(f"  Script: {prog['script']}")
    print(f"  Desc:   {prog['description']}")
    print(f"  Cmd:    {' '.join(cmd)}")
    print(f"{'='*80}\n")

    start = time.time()
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=False, timeout=300)
    elapsed = time.time() - start

    return result.returncode == 0, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Master Analysis Runner")
    parser.add_argument("transcription", nargs="?", default=str(DATA_DEFAULT),
                        help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--steps", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--program", type=str, default=None,
                        help="Run only this program by name (partial match)")
    args = parser.parse_args()

    steps_reduced = max(10000, args.steps // 3)  # use reduced steps for mutation/lifecycle

    print("=" * 80)
    print("  VOYNICH ENGINE — MASTER ANALYSIS SUITE")
    print("=" * 80)
    print(f"  Data:    {args.transcription}")
    print(f"  Steps:   {args.steps} (reduced: {steps_reduced} for heavy programs)")
    print(f"  Seed:    {args.seed}")
    print(f"  Programs: {len(PROGRAMS)}")
    print("=" * 80)

    programs_to_run = PROGRAMS
    if args.program:
        programs_to_run = [p for p in PROGRAMS if args.program.lower() in p["name"].lower()]
        if not programs_to_run:
            print(f"ERROR: No program matches '{args.program}'")
            sys.exit(1)

    results: list[tuple[str, bool, float]] = []
    for prog in programs_to_run:
        try:
            ok, elapsed = run_program(prog, args.transcription, args.steps, args.seed, steps_reduced)
            results.append((prog["name"], ok, elapsed))
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 300s")
            results.append((prog["name"], False, 300.0))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((prog["name"], False, 0.0))

    # Summary
    print(f"\n{'='*80}")
    print(f"  ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"  {'Program':<40} {'Status':>8} {'Time':>8}")
    print(f"  {'-'*40} {'-'*8} {'-'*8}")
    total_ok = 0
    for name, ok, elapsed in results:
        status = "OK" if ok else "FAILED"
        if ok:
            total_ok += 1
        print(f"  {name:<40} {status:>8} {elapsed:>7.1f}s")

    print(f"\n  {total_ok}/{len(results)} programs completed successfully.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()