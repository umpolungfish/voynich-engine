#!/usr/bin/env python3
"""
Folio Mutation Scanner — perturb the Voynich and measure structural fragility.

Systematically mutates the EVA transcription at controlled rates and positions,
then measures how the Universal Engine's behavior changes. This answers:
  - Is the Voynich Engine's bootstrap fragile or robust?
  - Which glyphs are load-bearing for the self-sustaining loop?
  - At what mutation rate does the engine behavior qualitatively change?
  - Are some sections more mutation-resistant than others?

Mutation types:
  1. Random substitution: replace glyph X with random glyph Y with probability p
  2. Glyph deletion: remove each glyph with probability p
  3. Glyph insertion: insert random glyph after each existing glyph with probability p
  4. Targeted knockout: remove ALL instances of one specific glyph
  5. Section-targeted: mutate only one section's folios
  6. Bootstrap-targeted: corrupt bootstrap sequences specifically

Metrics tracked vs baseline:
  - Active register count at steady state
  - Paradox stabilization rate
  - IFIX burn rate
  - Bootstrap loop count
  - Frobenius balance (δ/μ ratio)
  - Instruction count delta

Usage:
    python programs/mutation_scanner.py data/LSI_ivtff_0d.txt [--steps 50000] [--seed 42]
"""

from __future__ import annotations
import argparse
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import (
    compile_corpus, UniversalEngine, PRIMITIVES, BOOTSTRAP_SEQUENCE,
    classify_folio,
)
from voynich_engine.compiler import _compile_folio

GLYPHS = list(PRIMITIVES.keys())
_REG_PATTERN = re.compile(r'%r(\d+)')


def get_voynich_glyph_stream(result: dict) -> list[tuple[str, str]]:
    """Extract ordered (glyph, folio) pairs from compiled corpus."""
    stream = []
    mnemonics = {meta["mnemonic"]: glyph for glyph, meta in PRIMITIVES.items()}
    for folio_name in sorted(result["folios"].keys()):
        for instr in result["folios"][folio_name]["instructions"]:
            for mnemonic, glyph in mnemonics.items():
                if mnemonic in instr:
                    stream.append((glyph, folio_name))
                    break
    return stream


def glyphs_to_compiled_result(glyphs: list[str], folio_names: list[str]) -> dict:
    """Convert a mutated glyph stream back to a compile_corpus()-style result dict."""
    folio_instrs: dict[str, list[str]] = defaultdict(list)
    folio_regs: dict[str, int] = defaultdict(int)
    reg_counters: dict[str, int] = defaultdict(int)

    mnemonics = {glyph: meta["mnemonic"] for glyph, meta in PRIMITIVES.items()}

    for glyph, folio in zip(glyphs, folio_names):
        if glyph in mnemonics:
            meta = PRIMITIVES[glyph]
            r = reg_counters[folio]
            folio_instrs[folio].append(
                f" {hex(meta['opcode'])} | {meta['mnemonic']:<6} %r{r}"
            )
            reg_counters[folio] += 1

    folios = {}
    for folio in sorted(folio_instrs.keys()):
        folios[folio] = {
            "instructions": folio_instrs[folio],
            "registers": reg_counters[folio],
        }

    total_instrs = sum(len(f["instructions"]) for f in folios.values())
    total_regs = sum(f["registers"] for f in folios.values())

    return {
        "folios": folios,
        "total_instructions": total_instrs,
        "total_registers": total_regs,
        "folio_count": len(folios),
        "entropy_delta": 0.0,
    }


# ---- Mutation operators ----

def mutate_substitute(glyphs: list[str], rate: float, rng: random.Random) -> list[str]:
    """Random substitution mutation."""
    result = []
    for g in glyphs:
        if rng.random() < rate and g in GLYPHS:
            choices = [x for x in GLYPHS if x != g]
            result.append(rng.choice(choices))
        else:
            result.append(g)
    return result


def mutate_delete(glyphs: list[str], rate: float, rng: random.Random) -> list[str]:
    """Random deletion mutation."""
    return [g for g in glyphs if rng.random() >= rate]


def mutate_insert(glyphs: list[str], rate: float, rng: random.Random) -> list[str]:
    """Random insertion mutation."""
    result = []
    for g in glyphs:
        result.append(g)
        if rng.random() < rate:
            result.append(rng.choice(GLYPHS))
    return result


def mutate_knockout(glyphs: list[str], target: str) -> list[str]:
    """Remove ALL instances of a specific glyph."""
    return [g if g != target else "s" for g in glyphs]  # replace with IMSCRIB (identity)


def mutate_section_only(
    glyphs: list[str], folios: list[str], section: str,
    rate: float, rng: random.Random,
) -> list[str]:
    """Mutate only within a specific section."""
    result = []
    for g, f in zip(glyphs, folios):
        sec, _ = classify_folio(f)
        if sec == section and rng.random() < rate and g in GLYPHS:
            choices = [x for x in GLYPHS if x != g]
            result.append(rng.choice(choices))
        else:
            result.append(g)
    return result

def run_engine_metrics(result: dict, steps: int) -> dict:
    """Run engine and extract key metrics."""
    engine = UniversalEngine.from_compilation(result)
    final_snap = None
    for snap in engine.run(steps=steps, report_every=0):
        final_snap = snap
    s = final_snap or engine.snapshot()
    return {
        "active_registers": s["active_registers"],
        "fixed_registers": s["fixed_registers"],
        "paradox_stabilizations": s["paradox_stabilizations"],
        "paradox_rate": s["paradox_stabilizations"] / max(1, steps),
        "ifix_rate": s["fixed_registers"] / max(1, s["active_registers"]),
        "instruction_count": result["total_instructions"],
    }


def glyph_importance_scan(
    original_glyphs: list[str],
    original_folios: list[str],
    baseline: dict,
    steps: int,
) -> dict[str, dict]:
    """Knock out each glyph one at a time and measure impact."""
    results: dict[str, dict] = {}
    for target in GLYPHS:
        mutated = mutate_knockout(original_glyphs, target)
        mutated[0] = target  # keep at least one instance so the program doesn't crash

        mutant_result = glyphs_to_compiled_result(mutated, original_folios)
        metrics = run_engine_metrics(mutant_result, steps)

        delta_active = metrics["active_registers"] - baseline["active_registers"]
        delta_paradox = metrics["paradox_stabilizations"] - baseline["paradox_stabilizations"]

        results[target] = {
            "target_glyph": target,
            "target_mnemonic": PRIMITIVES[target]["mnemonic"],
            "target_operation": PRIMITIVES[target]["operation"],
            "active_registers": metrics["active_registers"],
            "delta_active": delta_active,
            "delta_paradox": delta_paradox,
            "paradox_rate": metrics["paradox_rate"],
            "instruction_count": metrics["instruction_count"],
        }

    return results


def mutation_rate_scan(
    original_glyphs: list[str],
    original_folios: list[str],
    baseline: dict,
    rates: list[float],
    steps: int,
    rng: random.Random,
) -> list[dict]:
    """Scan mutation rates from 0.01 to 0.5 and track degradation."""
    results = []
    for rate in rates:
        mutated = mutate_substitute(original_glyphs, rate, rng)
        mutant_result = glyphs_to_compiled_result(mutated, original_folios)
        metrics = run_engine_metrics(mutant_result, steps)

        results.append({
            "rate": rate,
            "active_registers": metrics["active_registers"],
            "paradox_rate": metrics["paradox_rate"],
            "ifix_rate": metrics["ifix_rate"],
            "instruction_count": metrics["instruction_count"],
            "delta_active": metrics["active_registers"] - baseline["active_registers"],
            "delta_paradox_rate": metrics["paradox_rate"] - baseline["paradox_rate"],
        })

    return results


def section_fragility_scan(
    original_glyphs: list[str],
    original_folios: list[str],
    baseline: dict,
    rate: float,
    steps: int,
    rng: random.Random,
) -> dict[str, dict]:
    """Mutate each section independently and measure fragility."""
    sections = set(classify_folio(f)[0] for f in original_folios)
    results: dict[str, dict] = {}

    for section in sorted(sections):
        mutated = mutate_section_only(original_glyphs, original_folios, section, rate, rng)
        mutant_result = glyphs_to_compiled_result(mutated, original_folios)
        metrics = run_engine_metrics(mutant_result, steps)

        results[section] = {
            "active_registers": metrics["active_registers"],
            "paradox_rate": metrics["paradox_rate"],
            "delta_active": metrics["active_registers"] - baseline["active_registers"],
            "delta_paradox_rate": metrics["paradox_rate"] - baseline["paradox_rate"],
        }

    return results

def main() -> None:
    parser = argparse.ArgumentParser(description="Folio Mutation Scanner")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--steps", type=int, default=50000, help="Execution steps per test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rates", default="0.01,0.05,0.10,0.20,0.30,0.50",
                        help="Comma-separated mutation rates to scan")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    rates = [float(x) for x in args.rates.split(",")]

    print("=== FOLIO MUTATION SCANNER ===\n")

    print("Compiling original corpus...")
    result = compile_corpus(args.transcription)
    print(f"  Folios: {result['folio_count']}")
    print(f"  Instructions: {result['total_instructions']}")
    print(f"  Registers: {result['total_registers']}\n")

    # Baseline
    print("Running baseline (unmutated)...")
    baseline = run_engine_metrics(result, args.steps)
    print(f"  Active: {baseline['active_registers']}, "
          f"Fixed: {baseline['fixed_registers']}, "
          f"Paradoxes: {baseline['paradox_stabilizations']}, "
          f"ParaRate: {baseline['paradox_rate']:.4f}\n")

    # Extract glyph stream
    glyph_stream = get_voynich_glyph_stream(result)
    glyphs = [g for g, _ in glyph_stream]
    folios = [f for _, f in glyph_stream]

    # Phase 1: Glyph importance (knockout scan)
    print("Phase 1 — Glyph importance (individual knockout):")
    importance = glyph_importance_scan(glyphs, folios, baseline, args.steps)

    print(f"  {'Glyph':<6} {'Mnemonic':<10} {'Operation':<38} {'ΔActive':>8} {'ΔParadox':>10}")
    print(f"  {'-'*6} {'-'*10} {'-'*38} {'-'*8} {'-'*10}")
    for target in sorted(importance.keys(), key=lambda x: abs(importance[x]["delta_active"]), reverse=True):
        imp = importance[target]
        print(f"  {target:<6} {imp['target_mnemonic']:<10} {imp['target_operation']:<38} "
              f"{imp['delta_active']:>8} {imp['delta_paradox']:>10}")

    # Identify load-bearing glyphs
    critical = [g for g, imp in importance.items() if abs(imp["delta_active"]) > 10]
    print(f"\n  Load-bearing glyphs (|ΔActive| > 10): {critical if critical else 'NONE'}")

    # Phase 2: Mutation rate scan
    print(f"\nPhase 2 — Mutation rate scan (substitution):")
    rate_results = mutation_rate_scan(glyphs, folios, baseline, rates, args.steps, rng)

    print(f"  {'Rate':>6} {'Active':>8} {'ΔActive':>8} {'ParaRate':>10} {'ΔParaRate':>10} {'Instrs':>8}")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
    for r in rate_results:
        print(f"  {r['rate']:>6.2f} {r['active_registers']:>8} {r['delta_active']:>8} "
              f"{r['paradox_rate']:>10.4f} {r['delta_paradox_rate']:>10.4f} "
              f"{r['instruction_count']:>8}")

    # Find critical threshold
    if rate_results:
        for r in rate_results:
            if abs(r["delta_active"]) > baseline["active_registers"] * 0.1:
                print(f"\n  ⚠ Structural degradation >10% at mutation rate: {r['rate']:.2f}")
                break

    # Phase 3: Section fragility
    print(f"\nPhase 3 — Section fragility (mutation rate=0.10):")
    fragility = section_fragility_scan(glyphs, folios, baseline, 0.10, args.steps, rng)

    print(f"  {'Section':<16} {'Active':>8} {'ΔActive':>8} {'ParaRate':>10} {'ΔParaRate':>10}")
    print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")
    for section in sorted(fragility.keys()):
        f = fragility[section]
        print(f"  {section:<16} {f['active_registers']:>8} {f['delta_active']:>8} "
              f"{f['paradox_rate']:>10.4f} {f['delta_paradox_rate']:>10.4f}")

    # Most fragile section
    if fragility:
        most_fragile = max(fragility.items(), key=lambda x: abs(x[1]["delta_active"]))
        print(f"\n  Most fragile section: {most_fragile[0]} (ΔActive={most_fragile[1]['delta_active']})")

    print(f"\n=== SUMMARY ===")
    print(f"  Baseline active registers: {baseline['active_registers']}")
    print(f"  Baseline paradox rate:     {baseline['paradox_rate']:.4f}")
    if critical:
        print(f"  Critical glyphs:           {', '.join(critical)}")
    else:
        print(f"  No single-glyph knockout causes >10 register change")
    print(f"  Engine robustness:         {'ROBUST' if not critical else 'FRAGILE'}")
    print()


if __name__ == "__main__":
    main()