#!/usr/bin/env python3
"""
Synthetic EVA Comparator — is the zero-entropy bootstrap unique to the Voynich?

Generates synthetic EVA-text streams with controlled statistical properties
and compiles/runs them through the Universal Engine to test:
  1. Is the zero-entropy delta a theorem of the engine or a property of the input?
  2. Does self-sustaining bootstrap require the specific Voynich distribution?
  3. At what statistical distance from the Voynich does the engine behavior change?

Synthetic generators:
  - uniform:     All 12 glyphs with equal probability
  - voynich_freq: Match the empirical Voynich glyph frequencies
  - markov_k:    k-th order Markov chain trained on Voynich bigrams/trigrams
  - shuffled:    Real Voynich folios with glyph order shuffled (preserve dist, destroy seq)
  - bootstrap_only: Only the bootstrap core repeated
  - frobenius_only: Only ch/sh (δ/μ) pairs
  - random_walk:   Random walk on the opcode graph (adjacent opcodes only)

Metrics compared against baseline Voynich:
  - Entropy delta (always 0 — tests if this is engine-invariant)
  - Active register ratio at saturation
  - IFIX burn rate
  - Paradox stabilization rate
  - Bootstrap loop detection count
  - Time to steady state

Usage:
    python programs/synthetic_comparator.py data/LSI_ivtff_0d.txt [--steps 100000]
"""

from __future__ import annotations
import argparse
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import (
    compile_corpus, UniversalEngine, PRIMITIVES, BOOTSTRAP_SEQUENCE,
)
from voynich_engine.compiler import _compile_folio


GLYPHS = list(PRIMITIVES.keys())
MNEMONICS = [meta["mnemonic"] for meta in PRIMITIVES.values()]


def get_voynich_frequencies(result: dict) -> dict[str, float]:
    """Compute empirical glyph frequencies from the compiled Voynich corpus."""
    total = 0
    counts: Counter = Counter()
    for folio_data in result["folios"].values():
        for instr in folio_data["instructions"]:
            for mnemonic in MNEMONICS:
                if mnemonic in instr:
                    glyph = [g for g, m in PRIMITIVES.items() if m["mnemonic"] == mnemonic][0]
                    counts[glyph] += 1
                    total += 1
                    break
    return {g: counts.get(g, 0) / max(1, total) for g in GLYPHS}


def get_voynich_bigrams(result: dict) -> dict[str, dict[str, float]]:
    """Build bigram transition matrix from Voynich corpus."""
    transitions: dict[str, Counter] = defaultdict(Counter)
    for folio_data in result["folios"].values():
        prev = None
        for instr in folio_data["instructions"]:
            for mnemonic in MNEMONICS:
                if mnemonic in instr:
                    glyph = [g for g, m in PRIMITIVES.items() if m["mnemonic"] == mnemonic][0]
                    if prev is not None:
                        transitions[prev][glyph] += 1
                    prev = glyph
                    break

    # Normalize
    matrix: dict[str, dict[str, float]] = {}
    for prev_glyph, counts in transitions.items():
        total = sum(counts.values())
        matrix[prev_glyph] = {g: c / total for g, c in counts.items()}
    return matrix


# ---- Synthetic generators ----

def gen_uniform(length: int, rng: random.Random) -> list[str]:
    return [rng.choice(GLYPHS) for _ in range(length)]


def gen_voynich_freq(freqs: dict[str, float], length: int, rng: random.Random) -> list[str]:
    glyphs = list(freqs.keys())
    weights = [freqs[g] for g in glyphs]
    return rng.choices(glyphs, weights=weights, k=length)


def gen_markov(bigrams: dict[str, dict[str, float]], length: int, rng: random.Random) -> list[str]:
    if not bigrams:
        return gen_uniform(length, rng)
    current = rng.choice(list(bigrams.keys()))
    result = [current]
    for _ in range(length - 1):
        transitions = bigrams.get(current)
        if transitions:
            glyphs = list(transitions.keys())
            weights = list(transitions.values())
            current = rng.choices(glyphs, weights=weights, k=1)[0]
        else:
            current = rng.choice(GLYPHS)
        result.append(current)
    return result

def gen_shuffled(glyphs: list[str], rng: random.Random) -> list[str]:
    """Shuffle an existing glyph sequence (preserve distribution, destroy order)."""
    shuffled = list(glyphs)
    rng.shuffle(shuffled)
    return shuffled


def gen_bootstrap_only(length: int) -> list[str]:
    core = list(BOOTSTRAP_SEQUENCE)
    return [core[i % len(core)] for i in range(length)]


def gen_frobenius_only(length: int, rng: random.Random) -> list[str]:
    """Only δ (ch) and μ (sh) alternating with slight randomness."""
    result = []
    for i in range(length):
        if rng.random() < 0.5:
            result.append("ch" if i % 2 == 0 else "sh")
        else:
            result.append("sh" if i % 2 == 0 else "ch")
    return result


def gen_random_walk(length: int, rng: random.Random) -> list[str]:
    """Random walk on opcode graph: only move to adjacent opcodes (±1 in opcode value)."""
    glyph_by_opcode = sorted(PRIMITIVES.items(), key=lambda x: x[1]["opcode"])
    opcode_to_glyph = {meta["opcode"]: g for g, meta in glyph_by_opcode}
    max_opcode = max(meta["opcode"] for meta in PRIMITIVES.values())

    current_opcode = rng.randint(0, max_opcode)
    result = [opcode_to_glyph[current_opcode]]
    for _ in range(length - 1):
        neighbors = []
        if current_opcode - 1 in opcode_to_glyph:
            neighbors.append(current_opcode - 1)
        if current_opcode + 1 in opcode_to_glyph:
            neighbors.append(current_opcode + 1)
        if not neighbors:
            neighbors = [current_opcode]
        current_opcode = rng.choice(neighbors)
        result.append(opcode_to_glyph[current_opcode])
    return result


# ---- Compilation of synthetic streams ----

def glyphs_to_instructions(glyphs: list[str]) -> tuple[list[str], int]:
    """Convert a glyph list to IMASM instruction lines (mimics compiler output)."""
    instructions = []
    reg = 0
    for glyph in glyphs:
        if glyph in PRIMITIVES:
            meta = PRIMITIVES[glyph]
            instructions.append(f" {hex(meta['opcode'])} | {meta['mnemonic']:<6} %r{reg}")
        reg += 1
    return instructions, reg


def compile_synthetic(glyphs: list[str], name: str = "synthetic") -> dict:
    """Package a synthetic glyph stream as a compile_corpus() result dict."""
    instructions, reg_count = glyphs_to_instructions(glyphs)
    return {
        "folios": {name: {"instructions": instructions, "registers": reg_count}},
        "total_instructions": len(instructions),
        "total_registers": reg_count,
        "folio_count": 1,
        "entropy_delta": 0.0,
    }


# ---- Metrics ----

def run_and_measure(result: dict, steps: int) -> dict:
    """Compile → run → measure key engine metrics."""
    engine = UniversalEngine.from_compilation(result)

    snapshots = []
    for snap in engine.run(steps=steps, report_every=max(1, steps // 10)):
        snapshots.append(snap)

    final = engine.snapshot()

    # Detect bootstrap loops: count how many times PC wraps to 0
    pc_wraps = sum(1 for s in snapshots if s["pc"] < 10 and s["step"] > 0)

    # Time to steady state: first step where active_registers doesn't change for 3 consecutive
    steady_state_step = steps
    for i in range(2, len(snapshots)):
        if (snapshots[i]["active_registers"] == snapshots[i-1]["active_registers"] ==
                snapshots[i-2]["active_registers"]):
            steady_state_step = snapshots[i]["step"]
            break

    return {
        "steps": steps,
        "final_active": final["active_registers"],
        "final_fixed": final["fixed_registers"],
        "final_paradox": final["paradox_stabilizations"],
        "entropy_delta": final["entropy_delta"],
        "paradox_rate": final["paradox_stabilizations"] / max(1, steps),
        "ifix_rate": final["fixed_registers"] / max(1, final["active_registers"]),
        "steady_state_step": steady_state_step,
        "pc_wraps": pc_wraps,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic EVA Comparator")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--steps", type=int, default=100000, help="Execution steps per test")
    parser.add_argument("--length", type=int, default=44445,
                        help="Length of synthetic streams (default: matches Voynich)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print("=== SYNTHETIC EVA COMPARATOR ===\n")

    # Compile real Voynich
    print("Compiling real Voynich corpus...")
    voynich_result = compile_corpus(args.transcription)
    voynich_freqs = get_voynich_frequencies(voynich_result)
    voynich_bigrams = get_voynich_bigrams(voynich_result)

    # Gather all Voynich glyphs for shuffling
    all_voynich_glyphs = []
    for folio_data in voynich_result["folios"].values():
        for instr in folio_data["instructions"]:
            for mnemonic in MNEMONICS:
                if mnemonic in instr:
                    glyph = [g for g, m in PRIMITIVES.items() if m["mnemonic"] == mnemonic][0]
                    all_voynich_glyphs.append(glyph)
                    break

    print(f"  Voynich: {voynich_result['total_instructions']} instructions, "
          f"{voynich_result['total_registers']} registers\n")

    # Baseline: real Voynich
    print("Running baseline (real Voynich)...")
    voynich_metrics = run_and_measure(voynich_result, args.steps)

    # Generate and test synthetic streams
    generators = {
        "uniform": lambda: gen_uniform(args.length, rng),
        "voynich_freq": lambda: gen_voynich_freq(voynich_freqs, args.length, rng),
        "markov_1": lambda: gen_markov(voynich_bigrams, args.length, rng),
        "shuffled": lambda: gen_shuffled(all_voynich_glyphs, rng),
        "bootstrap_only": lambda: gen_bootstrap_only(args.length),
        "frobenius_only": lambda: gen_frobenius_only(args.length, rng),
        "random_walk": lambda: gen_random_walk(args.length, rng),
    }

    all_metrics: dict[str, dict] = {"voynich_real": voynich_metrics}

    for name, gen_fn in generators.items():
        print(f"Running synthetic: {name}...")
        glyphs = gen_fn()
        synth_result = compile_synthetic(glyphs, name=f"synth_{name}")
        metrics = run_and_measure(synth_result, args.steps)
        all_metrics[name] = metrics

    # Display comparison table
    print(f"\n{'='*100}")
    print(f"{'Generator':<18} {'Active':>7} {'Fixed':>7} {'Paradox':>9} "
          f"{'ParaRate':>10} {'IFIX%':>8} {'SteadyStep':>11} {'PC_wraps':>9} {'ΔS':>6}")
    print(f"{'-'*18} {'-'*7} {'-'*7} {'-'*9} {'-'*10} {'-'*8} {'-'*11} {'-'*9} {'-'*6}")

    for name, m in all_metrics.items():
        print(
            f"{name:<18} {m['final_active']:>7} {m['final_fixed']:>7} "
            f"{m['final_paradox']:>9} {m['paradox_rate']:>10.4f} "
            f"{m['ifix_rate']:>8.3f} {m['steady_state_step']:>11} "
            f"{m['pc_wraps']:>9} {m['entropy_delta']:>6.1f}"
        )

    # Key findings
    print(f"\n=== KEY FINDINGS ===")

    # Is zero entropy universal?
    all_zero = all(m["entropy_delta"] == 0.0 for m in all_metrics.values())
    print(f"  Zero entropy across ALL inputs: {'YES (engine invariant)' if all_zero else 'NO (input-dependent)'}")

    # Does voynich_freq reproduce the real behavior?
    vf = all_metrics.get("voynich_freq", {})
    vr = all_metrics["voynich_real"]
    if vf:
        paradox_close = abs(vf.get("paradox_rate", 0) - vr["paradox_rate"]) < 0.01
        print(f"  Voynich-freq matches real paradox rate: {'YES' if paradox_close else 'NO'}")
        print(f"    Real paradox rate:  {vr['paradox_rate']:.4f}")
        print(f"    Freq-gen rate:      {vf.get('paradox_rate', 0):.4f}")

    # Bootstrap-only behavior
    bo = all_metrics.get("bootstrap_only", {})
    if bo:
        print(f"  Bootstrap-only reaches steady state at step: {bo.get('steady_state_step', 'N/A')}")
        print(f"  Bootstrap-only paradox rate: {bo.get('paradox_rate', 0):.4f}")

    # Shuffled vs real (tests sequential structure importance)
    sh = all_metrics.get("shuffled", {})
    if sh:
        active_diff = abs(sh.get("final_active", 0) - vr["final_active"])
        print(f"  Shuffled vs real active register diff: {active_diff}")
        print(f"    (Large diff → sequential structure matters)")

    print()


if __name__ == "__main__":
    main()
