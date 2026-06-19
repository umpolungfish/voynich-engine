#!/usr/bin/env python3
"""
Folio Topology Comparator — structural signature analysis per folio.

Computes per-folio structural fingerprints and compares them:
  1. Opcode distribution (which categorical operations dominate each folio)
  2. Instruction-pair bigrams (sequential structure of the IMASM stream)
  3. Register reuse depth (how far apart are re-references to the same register)
  4. Frobenius balance ratio (FSPLIT vs FFUSE — δ vs μ symmetry)
  5. Dialetheia fraction (EVALT/EVALF/ENGAGR density)
  6. Cross-folio structural distance matrix (Jensen-Shannon divergence)

The hypothesis from the structural analysis:
  - Botanical/Pharmaceutical: network topology (Þ_6) → uniform opcode spread
  - Cosmological: imscriptive (Þ_O) → high FSPLIT/FFUSE balance, closed loops
  - Biological: nested (Þ_K) → deep register reuse, high ENGAGR
  - Recipe: adjoint (Ř_Ť) → sequential AFWD/AREV pairs, high CLINK

Usage:
    python programs/folio_comparator.py data/LSI_ivtff_0d.txt [--top-n 20]
"""

from __future__ import annotations
import argparse
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import compile_corpus, classify_folio, PRIMITIVES
from voynich_engine.compiler import _extract


MNEMONIC_TO_GLYPH = {meta["mnemonic"]: glyph for glyph, meta in PRIMITIVES.items()}
ALL_GLYPHS = list(PRIMITIVES.keys())


def glyphs_from_instructions(instructions: list[str]) -> list[str]:
    """Extract ordered glyph list from compiled instructions."""
    glyphs = []
    for instr in instructions:
        for mnemonic in ["VINIT", "TANCH", "AFWD", "AREV", "CLINK", "IMSCRIB",
                         "FSPLIT", "FFUSE", "EVALT", "EVALF", "ENGAGR", "IFIX"]:
            if mnemonic in instr:
                glyphs.append(MNEMONIC_TO_GLYPH[mnemonic])
                break
    return glyphs


def opcode_distribution(glyphs: list[str]) -> dict[str, float]:
    """Normalize glyph counts to a probability distribution."""
    if not glyphs:
        return {g: 0.0 for g in ALL_GLYPHS}
    counts = Counter(glyphs)
    total = len(glyphs)
    return {g: counts.get(g, 0) / total for g in ALL_GLYPHS}


def bigram_distribution(glyphs: list[str]) -> Counter:
    """Count consecutive glyph pairs."""
    return Counter(zip(glyphs[:-1], glyphs[1:]))


def frobenius_balance(glyphs: list[str]) -> float:
    """Ratio of FSPLIT (δ) to FFUSE (μ). 1.0 = perfect balance."""
    splits = glyphs.count("ch")
    fuses = glyphs.count("sh")
    if fuses == 0:
        return float("inf") if splits > 0 else 1.0
    return splits / fuses


def dialetheia_fraction(glyphs: list[str]) -> float:
    """Fraction of lattice opcodes (t, k, r) in the stream."""
    if not glyphs:
        return 0.0
    lattice = sum(1 for g in glyphs if g in ("t", "k", "r"))
    return lattice / len(glyphs)


def register_reuse_depth(instructions: list[str]) -> list[int]:
    """
    For each register reference, compute how many instructions back it was
    last seen. Returns list of reuse depths (0 for first occurrence).
    """
    last_seen: dict[int, int] = {}
    depths = []
    for idx, instr in enumerate(instructions):
        import re
        regs = [int(x) for x in re.findall(r'%r(\d+)', instr)]
        for r in regs:
            if r in last_seen:
                depths.append(idx - last_seen[r])
            else:
                depths.append(0)
            last_seen[r] = idx
    return depths


def jensen_shannon(p: dict[str, float], q: dict[str, float]) -> float:
    """Jensen-Shannon divergence between two distributions (base 2)."""
    keys = set(p.keys()) | set(q.keys())
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: dict, b: dict) -> float:
        total = 0.0
        for k in keys:
            ak = a.get(k, 0.0)
            bk = b.get(k, 0.0)
            if ak > 0 and bk > 0:
                total += ak * math.log2(ak / bk)
        return total

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)

def compute_folio_profiles(result: dict) -> dict[str, dict]:
    """Compute full structural profile for each folio."""
    profiles: dict[str, dict] = {}
    for folio_name, folio_data in sorted(result["folios"].items()):
        instructions = folio_data["instructions"]
        glyphs = glyphs_from_instructions(instructions)

        dist = opcode_distribution(glyphs)
        bigrams = bigram_distribution(glyphs)
        depths = register_reuse_depth(instructions)

        # Top 3 bigrams
        top_bigrams = bigrams.most_common(3)

        profiles[folio_name] = {
            "glyphs": glyphs,
            "distribution": dist,
            "frobenius_balance": frobenius_balance(glyphs),
            "dialetheia_fraction": dialetheia_fraction(glyphs),
            "avg_reuse_depth": sum(depths) / max(1, len(depths)),
            "max_reuse_depth": max(depths) if depths else 0,
            "top_bigrams": top_bigrams,
            "section": classify_folio(folio_name)[0],
            "register_count": folio_data["registers"],
        }

    return profiles


def section_distance_matrix(profiles: dict[str, dict]) -> dict[tuple[str, str], float]:
    """Compute JS divergence between aggregate section distributions."""
    # Aggregate distributions per section
    section_dists: dict[str, list[dict]] = defaultdict(list)
    for prof in profiles.values():
        section_dists[prof["section"]].append(prof["distribution"])

    section_avg: dict[str, dict] = {}
    for section, dists in section_dists.items():
        avg = {g: 0.0 for g in ALL_GLYPHS}
        for d in dists:
            for g in ALL_GLYPHS:
                avg[g] += d.get(g, 0.0)
        for g in ALL_GLYPHS:
            avg[g] /= len(dists)
        section_avg[section] = avg

    # Pairwise JS divergence
    sections = sorted(section_avg.keys())
    matrix: dict[tuple[str, str], float] = {}
    for i, s1 in enumerate(sections):
        for s2 in sections[i:]:
            js = jensen_shannon(section_avg[s1], section_avg[s2])
            matrix[(s1, s2)] = js
            matrix[(s2, s1)] = js

    return matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Folio Topology Comparator")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--top-n", type=int, default=20,
                        help="Show top N folios for each metric")
    args = parser.parse_args()

    print("=== FOLIO TOPOLOGY COMPARATOR ===\n")

    print("Compiling corpus...")
    result = compile_corpus(args.transcription)
    print(f"  Folios: {result['folio_count']}\n")

    # Phase 1: Compute per-folio profiles
    print("Phase 1 — Computing per-folio structural profiles...")
    profiles = compute_folio_profiles(result)
    print(f"  Profiles computed for {len(profiles)} folios.\n")

    # Phase 2: Rank folios by key metrics
    print("Phase 2 — Folio rankings:")

    # Frobenius balance (closest to 1.0)
    by_fb = sorted(profiles.items(),
                   key=lambda x: abs(x[1]["frobenius_balance"] - 1.0))
    print(f"\n  Frobenius balance (closest to δ/μ = 1.0):")
    print(f"  {'Folio':<10} {'Section':<16} {'δ/μ':>8} {'Regs':>6}")
    print(f"  {'-'*10} {'-'*16} {'-'*8} {'-'*6}")
    for name, prof in by_fb[:args.top_n]:
        fb = prof["frobenius_balance"]
        fb_str = f"{fb:.3f}" if fb != float("inf") else "∞"
        print(f"  {name:<10} {prof['section']:<16} {fb_str:>8} {prof['register_count']:>6}")

    # Dialetheia fraction (highest)
    by_dial = sorted(profiles.items(), key=lambda x: x[1]["dialetheia_fraction"], reverse=True)
    print(f"\n  Dialetheia fraction (highest lattice density):")
    print(f"  {'Folio':<10} {'Section':<16} {'DialFrac':>10} {'Regs':>6}")
    print(f"  {'-'*10} {'-'*16} {'-'*10} {'-'*6}")
    for name, prof in by_dial[:args.top_n]:
        print(f"  {name:<10} {prof['section']:<16} {prof['dialetheia_fraction']:>10.4f} "
              f"{prof['register_count']:>6}")

    # Register reuse depth (deepest = most nested)
    by_depth = sorted(profiles.items(), key=lambda x: x[1]["max_reuse_depth"], reverse=True)
    print(f"\n  Register reuse depth (deepest nesting):")
    print(f"  {'Folio':<10} {'Section':<16} {'MaxDepth':>10} {'AvgDepth':>10} {'Regs':>6}")
    print(f"  {'-'*10} {'-'*16} {'-'*10} {'-'*10} {'-'*6}")
    for name, prof in by_depth[:args.top_n]:
        print(f"  {name:<10} {prof['section']:<16} {prof['max_reuse_depth']:>10} "
              f"{prof['avg_reuse_depth']:>10.2f} {prof['register_count']:>6}")

    # Phase 3: Section distance matrix
    print(f"\nPhase 3 — Section structural distance matrix (Jensen-Shannon):")
    dist_matrix = section_distance_matrix(profiles)
    sections = sorted(set(p["section"] for p in profiles.values()))
    header = "  {:<16}".format("") + "".join(f"{s:>14}" for s in sections)
    print(header)
    for s1 in sections:
        row = f"  {s1:<16}"
        for s2 in sections:
            val = dist_matrix.get((s1, s2), 0.0)
            row += f"{val:>14.6f}"
        print(row)

    # Phase 4: Aggregate section statistics
    print(f"\nPhase 4 — Aggregate section statistics:")
    section_stats: dict[str, list[dict]] = defaultdict(list)
    for prof in profiles.values():
        section_stats[prof["section"]].append(prof)

    print(f"  {'Section':<16} {'Folios':>6} {'AvgFrob':>10} {'AvgDial':>10} {'AvgDepth':>10}")
    print(f"  {'-'*16} {'-'*6} {'-'*10} {'-'*10} {'-'*10}")
    for section in sorted(section_stats.keys()):
        profs = section_stats[section]
        avg_fb = sum(p["frobenius_balance"] for p in profs
                     if p["frobenius_balance"] != float("inf")) / max(1, len(profs))
        avg_dial = sum(p["dialetheia_fraction"] for p in profs) / len(profs)
        avg_depth = sum(p["avg_reuse_depth"] for p in profs) / len(profs)
        print(f"  {section:<16} {len(profs):>6} {avg_fb:>10.3f} "
              f"{avg_dial:>10.4f} {avg_depth:>10.2f}")

    print(f"\n=== SUMMARY ===")
    # Check structural predictions
    print(f"  Botanical/Pharm section folios: {len(section_stats.get('botanical', []))}")
    print(f"  Cosmological section folios:    {len(section_stats.get('cosmological', []))}")
    print(f"  Biological section folios:      {len(section_stats.get('biological', []))}")
    print(f"  Balneological section folios:   {len(section_stats.get('balneological', []))}")
    print()


if __name__ == "__main__":
    main()
