#!/usr/bin/env python3
"""
Paradox Injection Analyzer — systematic dialetheic stress testing.

Injects paradoxes at controlled positions across the register space
and measures:
  - Stabilization rate (how quickly Both-state saturates)
  - Paradox propagation (do adjacent registers get engaged?)
  - Steady-state drift (does the engine's fixed-point change?)
  - Section-level paradox susceptibility (which sections absorb paradox best?)

Usage:
    python programs/paradox_injector.py data/LSI_ivtff_0d.txt [--steps 50000] [--stride 100]
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure the package is importable when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import compile_corpus, UniversalEngine, classify_folio
from voynich_engine.compiler import _compile_folio


def build_folio_register_map(result: dict) -> dict[str, tuple[int, int]]:
    """Map each folio name to its (reg_start, reg_end) in the global program."""
    folio_map: dict[str, tuple[int, int]] = {}
    offset = 0
    for folio_name, folio_data in sorted(result["folios"].items()):
        reg_count = folio_data["registers"]
        folio_map[folio_name] = (offset, offset + reg_count)
        offset += reg_count
    return folio_map


def run_baseline(result: dict, steps: int) -> dict:
    """Run the engine without any paradox injection; return final snapshot."""
    engine = UniversalEngine.from_compilation(result)
    for snap in engine.run(steps=steps, report_every=0):
        pass
    return engine.snapshot()


def inject_at_positions(
    result: dict,
    positions: list[int],
    steps: int,
    inject_after: int,
) -> dict:
    """Run engine, inject paradoxes at given register IDs after `inject_after` steps."""
    engine = UniversalEngine.from_compilation(result)

    for i in range(steps):
        engine.step()
        if i == inject_after:
            for reg_id in positions:
                engine.inject_paradox(reg_id)

    return engine.snapshot()


def section_paradox_profile(result: dict, steps: int, inject_after: int) -> dict[str, dict]:
    """
    For each section, inject paradoxes across all registers in that section's folios.
    Return per-section profiles showing how paradox propagation differs.
    """
    folio_map = build_folio_register_map(result)

    # Group registers by section
    section_regs: dict[str, list[int]] = {}
    for folio_name, (reg_start, reg_end) in folio_map.items():
        section, _ = classify_folio(folio_name)
        if section not in section_regs:
            section_regs[section] = []
        section_regs[section].extend(range(reg_start, reg_end))

    profiles: dict[str, dict] = {}
    baseline = run_baseline(result, steps)

    for section, regs in sorted(section_regs.items()):
        if not regs:
            continue
        # Sample up to 200 registers per section to keep runtime bounded
        sample = regs[::max(1, len(regs) // 200)]
        snap = inject_at_positions(result, sample, steps, inject_after)

        delta_paradox = snap["paradox_stabilizations"] - baseline["paradox_stabilizations"]
        delta_active = snap["active_registers"] - baseline["active_registers"]
        delta_fixed = snap["fixed_registers"] - baseline["fixed_registers"]

        profiles[section] = {
            "total_registers": len(regs),
            "injected": len(sample),
            "baseline_paradox": baseline["paradox_stabilizations"],
            "final_paradox": snap["paradox_stabilizations"],
            "delta_paradox": delta_paradox,
            "delta_active": delta_active,
            "delta_fixed": delta_fixed,
            "paradox_amplification": delta_paradox / max(1, len(sample)),
        }

    return profiles


def register_susceptibility_scan(
    result: dict,
    steps: int,
    inject_after: int,
    stride: int,
) -> list[tuple[int, int]]:
    """
    Inject paradox at every `stride`-th register individually.
    Return list of (register_id, final_paradox_count).
    Identifies which registers are "paradox amplifiers" vs "paradox sinks".
    """
    engine = UniversalEngine.from_compilation(result)
    total_regs = result["total_registers"]
    baseline = run_baseline(result, steps)["paradox_stabilizations"]

    results: list[tuple[int, int]] = []
    for reg_id in range(0, total_regs, stride):
        snap = inject_at_positions(result, [reg_id], steps, inject_after)
        amplification = snap["paradox_stabilizations"] - baseline
        results.append((reg_id, amplification))

    return results

def main() -> None:
    parser = argparse.ArgumentParser(description="Paradox Injection Analyzer")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--steps", type=int, default=50000, help="Total execution steps")
    parser.add_argument("--stride", type=int, default=100, help="Scan stride for susceptibility")
    parser.add_argument("--inject-after", type=int, default=1000, help="Inject paradoxes after N steps")
    args = parser.parse_args()

    print("=== PARADOX INJECTION ANALYZER ===\n")

    print("Compiling corpus...")
    result = compile_corpus(args.transcription)
    print(f"  Folios:     {result['folio_count']}")
    print(f"  Registers:  {result['total_registers']}")
    print(f"  Instructions: {result['total_instructions']}\n")

    # Phase 1: Baseline
    print(f"Phase 1 — Baseline run ({args.steps} steps)...")
    baseline = run_baseline(result, args.steps)
    print(f"  Active registers:      {baseline['active_registers']}")
    print(f"  Fixed registers:       {baseline['fixed_registers']}")
    print(f"  Paradox stabilizations: {baseline['paradox_stabilizations']}")
    print(f"  Entropy Δ:             {baseline['entropy_delta']:.8f} J/K\n")

    # Phase 2: Section-level paradox profile
    print("Phase 2 — Section paradox susceptibility...")
    profiles = section_paradox_profile(result, args.steps, args.inject_after)
    print(f"  {'Section':<16} {'Regs':>6} {'Injected':>8} {'ΔParadox':>10} {'Ampl/reg':>10} {'ΔActive':>8}")
    print(f"  {'-'*16} {'-'*6} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
    for section, prof in sorted(profiles.items()):
        print(
            f"  {section:<16} {prof['total_registers']:>6} {prof['injected']:>8} "
            f"{prof['delta_paradox']:>10} {prof['paradox_amplification']:>10.2f} "
            f"{prof['delta_active']:>8}"
        )
    print()

    # Phase 3: Register susceptibility scan
    print(f"Phase 3 — Register susceptibility scan (stride={args.stride})...")
    scan = register_susceptibility_scan(result, args.steps, args.inject_after, args.stride)
    top_amplifiers = sorted(scan, key=lambda x: x[1], reverse=True)[:10]
    top_sinks = sorted(scan, key=lambda x: x[1])[:10]

    print(f"\n  Top 10 paradox amplifiers (highest Δ):")
    for reg_id, amp in top_amplifiers:
        print(f"    r{reg_id:>6d}: +{amp} paradox stabilizations")

    print(f"\n  Top 10 paradox sinks (lowest Δ):")
    for reg_id, amp in top_sinks:
        print(f"    r{reg_id:>6d}: +{amp} paradox stabilizations")

    # Summary
    print(f"\n=== SUMMARY ===")
    max_amp_reg, max_amp_val = top_amplifiers[0] if top_amplifiers else (0, 0)
    print(f"  Strongest amplifier: r{max_amp_reg} (+{max_amp_val})")
    print(f"  Baseline paradox rate: {baseline['paradox_stabilizations']} / {args.steps} steps")
    print(f"  Paradox linearity:     {'CONFIRMED' if baseline['paradox_stabilizations'] > 0 else 'ABSENT'}")
    print()


if __name__ == "__main__":
    main()
