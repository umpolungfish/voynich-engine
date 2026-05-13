#!/usr/bin/env python3
"""
Bootstrap Cycle Explorer — locating and classifying Frobenius loops in the Voynich.

Two bootstrap patterns are searched:

  1. The DOMINANT 12-glyph Frobenius cycle (observed in compiled bigram data):
     o → e → a → d → s → t → k → r → y → ch → sh → (o)
     ISCRIB(VINIT) → AFWD → AREV → CLINK → ISCRIB → EVALT → EVALF → ENGAGR → IFIX → FSPLIT → FFUSE → (VINIT)

  2. The README-documented 8-glyph bootstrap core:
     s → a → ch → e → sh → d → y → (s)
     ISCRIB → AREV → FSPLIT → AFWD → FFUSE → CLINK → IFIX → (ISCRIB)

The dominant 12-cycle is the engine-level loop that emerges from the bigram
transition matrix. Both patterns are searched at the compiled glyph level.

Also performs:
  - Bigram transition matrix analysis (Markov chain structure)
  - Cross-folio bootstrap closure detection
  - Section-level cycle density comparison
  - Spectral gap analysis of the transition matrix

Usage:
    python programs/bootstrap_explorer.py data/LSI_ivtff_0d.txt [--max-mismatches 2]
"""

from __future__ import annotations
import argparse
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import compile_corpus, PRIMITIVES, classify_folio

MNEMONIC_TO_GLYPH = {meta["mnemonic"]: glyph for glyph, meta in PRIMITIVES.items()}
ALL_GLYPHS = list(PRIMITIVES.keys())

# The dominant 12-glyph Frobenius cycle (observed from bigram analysis)
DOMINANT_CYCLE = ['o', 'e', 'a', 'd', 's', 't', 'k', 'r', 'y', 'ch', 'sh']

# The README-documented 8-glyph bootstrap core
BOOTSTRAP_CORE = ['s', 'a', 'ch', 'e', 'sh', 'd', 'y', 's']


def extract_glyph_stream(result: dict) -> list[str]:
    """Build ordered glyph stream from compiled instructions."""
    glyphs = []
    for folio_name in sorted(result["folios"].keys()):
        for instr in result["folios"][folio_name]["instructions"]:
            for mnemonic, glyph in MNEMONIC_TO_GLYPH.items():
                if mnemonic in instr:
                    glyphs.append(glyph)
                    break
    return glyphs


def build_bigram_matrix(glyphs: list[str]) -> dict[str, dict[str, float]]:
    """Build normalized bigram transition matrix."""
    transitions: dict[str, Counter] = defaultdict(Counter)
    for a, b in zip(glyphs[:-1], glyphs[1:]):
        transitions[a][b] += 1

    matrix: dict[str, dict[str, float]] = {}
    for glyph, counts in transitions.items():
        total = sum(counts.values())
        matrix[glyph] = {g: c / total for g, c in counts.items()}
    return matrix


def find_cycle_in_stream(
    glyphs: list[str],
    cycle: list[str],
    max_mismatches: int = 2,
    allow_wrapping: bool = True,
) -> list[dict]:
    """
    Search for a repeating cycle in the glyph stream.
    The cycle can wrap (e.g., [o,e,a,d,s,t,k,r,y,ch,sh] repeats as o,e,a,d,...).
    """
    c_len = len(cycle)
    matches = []

    search_range = len(glyphs) - c_len + 1
    for i in range(search_range):
        window = glyphs[i : i + c_len]
        mismatches = 0
        for j in range(c_len):
            expected = cycle[j % c_len]
            if window[j] != expected:
                mismatches += 1
                if mismatches > max_mismatches:
                    break

        if mismatches <= max_mismatches:
            matches.append({
                "position": i,
                "sequence": list(window),
                "mismatches": mismatches,
            })

    return matches


def spectral_gap(matrix: dict[str, dict[str, float]]) -> float:
    """
    Compute the spectral gap of the bigram transition matrix.
    The gap between λ₁=1 and |λ₂| measures mixing rate.
    For a perfectly periodic chain, gap → 0 (slow mixing).
    For a random chain, gap → 1 (fast mixing).

    Uses power iteration to estimate |λ₂|.
    """
    glyphs = sorted(matrix.keys())
    n = len(glyphs)
    if n < 2:
        return 0.0

    idx = {g: i for i, g in enumerate(glyphs)}

    # Stationary distribution (proportional to row sums of counts)
    # Use uniform as initial
    pi = [1.0 / n] * n

    # Power iteration for dominant eigenvector (stationary distribution)
    for _ in range(200):
        new_pi = [0.0] * n
        for g_from in glyphs:
            for g_to, prob in matrix.get(g_from, {}).items():
                new_pi[idx[g_to]] += pi[idx[g_from]] * prob
        total = sum(new_pi)
        if total > 0:
            pi = [x / total for x in new_pi]

    # Now estimate λ₂ by looking at convergence rate
    # Perturb pi slightly and measure decay
    pi2 = list(pi)
    if n > 1:
        pi2[0] += 0.01
        pi2[1] -= 0.01
    total2 = sum(pi2)
    pi2 = [x / total2 for x in pi2]

    decay_rate = 0.0
    for iteration in range(50):
        new_pi2 = [0.0] * n
        for g_from in glyphs:
            for g_to, prob in matrix.get(g_from, {}).items():
                new_pi2[idx[g_to]] += pi2[idx[g_from]] * prob
        total2 = sum(new_pi2)
        if total2 > 0:
            new_pi2 = [x / total2 for x in new_pi2]

        # Distance from stationary
        dist_before = sum(abs(pi2[i] - pi[i]) for i in range(n))
        dist_after = sum(abs(new_pi2[i] - pi[i]) for i in range(n))

        if dist_before > 1e-10:
            decay_rate = dist_after / dist_before

        pi2 = new_pi2

    # Spectral gap ≈ 1 - |λ₂| where |λ₂| ≈ decay_rate
    return max(0.0, 1.0 - decay_rate)

def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Cycle Explorer")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--max-mismatches", type=int, default=2,
                        help="Max mismatches for near-match detection")
    args = parser.parse_args()

    print("=== BOOTSTRAP CYCLE EXPLORER ===\n")

    print("Compiling corpus...")
    result = compile_corpus(args.transcription)
    print(f"  Folios:   {result['folio_count']}")
    print(f"  Instructions: {result['total_instructions']}")
    print(f"  Registers:    {result['total_registers']}\n")

    # Extract glyph stream
    glyphs = extract_glyph_stream(result)
    print(f"  Total glyphs: {len(glyphs)}")
    print(f"  First 40:     {' '.join(glyphs[:40])}\n")

    # Phase 1: Bigram transition matrix
    print("Phase 1 — Bigram transition matrix:")
    matrix = build_bigram_matrix(glyphs)
    for glyph in sorted(matrix.keys()):
        row = matrix[glyph]
        top = sorted(row.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ', '.join(f"{g}({p:.2f})" for g, p in top)
        print(f"  {glyph:>4} → {top_str}")

    print(f"\n  Dominant cycle (bigram chain):")
    cycle_str = ' → '.join(DOMINANT_CYCLE) + ' → (o)'
    print(f"    {cycle_str}")

    # Verify each link in the dominant cycle
    print(f"\n  Cycle link verification:")
    for i in range(len(DOMINANT_CYCLE)):
        g_from = DOMINANT_CYCLE[i]
        g_to = DOMINANT_CYCLE[(i + 1) % len(DOMINANT_CYCLE)]
        prob = matrix.get(g_from, {}).get(g_to, 0.0)
        print(f"    {g_from:>4} → {g_to:>4}: p={prob:.4f}")

    # Phase 2: Search for dominant 11-cycle
    print(f"\nPhase 2 — Dominant 11-glyph cycle search:")
    matches_12 = find_cycle_in_stream(glyphs, DOMINANT_CYCLE, max_mismatches=args.max_mismatches)
    exact_12 = sum(1 for m in matches_12 if m["mismatches"] == 0)
    near_12 = sum(1 for m in matches_12 if m["mismatches"] > 0)
    print(f"  Exact matches: {exact_12}")
    print(f"  Near matches:  {near_12}")
    print(f"  Hit rate:      {len(matches_12)/max(1,len(glyphs))*1000:.3f} per 1000 glyphs")

    if matches_12:
        # Show distribution across folios
        folio_offsets = {}
        offset = 0
        for folio_name in sorted(result["folios"].keys()):
            count = sum(1 for _ in result["folios"][folio_name]["instructions"]
                       if any(m in _ for m in MNEMONIC_TO_GLYPH))
            folio_offsets[folio_name] = (offset, offset + count)
            offset += count

        section_matches: dict[str, int] = defaultdict(int)
        for m in matches_12[:100]:  # sample first 100
            pos = m["position"]
            for fn, (start, end) in folio_offsets.items():
                if start <= pos < end:
                    sec, _ = classify_folio(fn)
                    section_matches[sec] += 1
                    break

        print(f"\n  Cycle match distribution by section (first 100):")
        for sec in sorted(section_matches.keys()):
            print(f"    {sec:<16}: {section_matches[sec]}")

    # Phase 3: 8-glyph bootstrap core
    print(f"\nPhase 3 — 8-glyph bootstrap core search:")
    core_matches = find_cycle_in_stream(glyphs, BOOTSTRAP_CORE, max_mismatches=args.max_mismatches)
    exact_core = sum(1 for m in core_matches if m["mismatches"] == 0)
    near_core = sum(1 for m in core_matches if m["mismatches"] > 0)
    print(f"  Exact matches: {exact_core}")
    print(f"  Near matches:  {near_core}")

    # Phase 4: Cross-folio cycle closure
    print(f"\nPhase 4 — Cross-folio cycle closures:")
    offset = 0
    cross_folio_matches = 0
    for folio_name in sorted(result["folios"].keys()):
        count = sum(1 for instr in result["folios"][folio_name]["instructions"]
                   if any(m in instr for m in MNEMONIC_TO_GLYPH))
        # Check boundary: last 6 glyphs of this folio + first 6 of next
        if offset > 6 and offset + 6 < len(glyphs):
            boundary = glyphs[offset-6:offset+6]
            b_matches = find_cycle_in_stream(boundary, DOMINANT_CYCLE, max_mismatches=1)
            cross_folio_matches += len(b_matches)
        offset += count

    print(f"  Cross-folio cycle closures found: {cross_folio_matches}")

    # Phase 5: Spectral gap
    print(f"\nPhase 5 — Spectral gap analysis:")
    gap = spectral_gap(matrix)
    print(f"  Spectral gap: {gap:.6f}")
    if gap < 0.1:
        print(f"  Interpretation: NEARLY PERIODIC (slow mixing → structured cycle)")
    elif gap < 0.3:
        print(f"  Interpretation: SEMI-PERIODIC (moderate mixing)")
    else:
        print(f"  Interpretation: FAST MIXING (random-like)")

    # Phase 6: Cycle persistence
    print(f"\nPhase 6 — Cycle persistence (longest exact run):")
    longest_run = 0
    current_run = 0
    best_start = 0
    for i, g in enumerate(glyphs):
        expected = DOMINANT_CYCLE[i % len(DOMINANT_CYCLE)]
        if g == expected:
            current_run += 1
            if current_run > longest_run:
                longest_run = current_run
                best_start = i - current_run + 1
        else:
            current_run = 0

    print(f"  Longest exact cycle run: {longest_run} glyphs ({longest_run/len(DOMINANT_CYCLE):.1f} complete cycles)")
    print(f"  Run position: glyphs {best_start}–{best_start+longest_run}")

    print(f"\n=== SUMMARY ===")
    print(f"  Dominant 11-cycle exact matches: {exact_12}")
    print(f"  8-glyph bootstrap exact matches: {exact_core}")
    print(f"  Cross-folio closures:           {cross_folio_matches}")
    print(f"  Spectral gap:                   {gap:.6f}")
    print(f"  Longest cycle run:              {longest_run} glyphs")
    print()


if __name__ == "__main__":
    main()