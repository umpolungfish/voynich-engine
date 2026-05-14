#!/usr/bin/env python3
"""
Bootstrap Cycle Explorer — locating and classifying Frobenius loops in the Voynich.

Two bootstrap patterns are searched:

  1. The DOMINANT 11-glyph Frobenius cycle (observed in compiled bigram data):
     o → e → a → d → s → t → k → r → y → ch → sh → (o)
     VINIT → AFWD → AREV → CLINK → ISCRIB → EVALT → EVALF → ENGAGR → IFIX → FSPLIT → FFUSE → (VINIT)

  2. The README-documented 7-glyph bootstrap core:
     s → a → ch → e → sh → d → y → (s)
     ISCRIB → AREV → FSPLIT → AFWD → FFUSE → CLINK → IFIX → (ISCRIB)

The dominant 11-cycle is the engine-level loop that emerges from the bigram
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
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import compile_corpus, PRIMITIVES, classify_folio

MNEMONIC_TO_GLYPH = {meta["mnemonic"]: glyph for glyph, meta in PRIMITIVES.items()}
ALL_GLYPHS = list(PRIMITIVES.keys())

# The dominant 12-glyph Frobenius cycle (observed from bigram analysis)
DOMINANT_CYCLE = ['o', 'e', 'a', 'd', 's', 't', 'k', 'r', 'y', 'ch', 'sh']

# The README-documented 7-glyph bootstrap core (trailing 's' in BOOTSTRAP_SEQUENCE is notation only)
BOOTSTRAP_CORE = ['s', 'a', 'ch', 'e', 'sh', 'd', 'y']


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

def dominant_cycle_from_matrix(matrix: dict[str, dict[str, float]], length: int = 11) -> list[str]:
    """Greedy search for the strongest closed cycle of given length.

    Tries every glyph as start, builds a chain by always picking the highest-prob
    unvisited successor, then closes back to start. Returns the cycle with the
    highest geometric mean transition probability, or [] if none closes.
    """
    best_cycle: list[str] = []
    best_geo = -1.0

    for start in matrix:
        cycle = [start]
        visited = {start}
        current = start
        probs: list[float] = []
        for _ in range(length - 1):
            row = matrix.get(current, {})
            candidates = sorted(
                ((g, p) for g, p in row.items() if g not in visited),
                key=lambda x: x[1], reverse=True,
            )
            if not candidates:
                break
            g, p = candidates[0]
            cycle.append(g)
            visited.add(g)
            probs.append(p)
            current = g
        close_prob = matrix.get(current, {}).get(start, 0.0)
        probs.append(close_prob)
        if len(cycle) == length and all(p > 0 for p in probs):
            geo = math.exp(sum(math.log(p) for p in probs) / len(probs))
            if geo > best_geo:
                best_geo = geo
                best_cycle = cycle[:]

    return best_cycle


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

    # Build folio offset map once; reused in Phases 2, 7, 8
    folio_offsets: dict[str, tuple[int, int]] = {}
    _off = 0
    for _fn in sorted(result["folios"].keys()):
        _cnt = sum(1 for _ in result["folios"][_fn]["instructions"]
                   if any(m in _ for m in MNEMONIC_TO_GLYPH))
        folio_offsets[_fn] = (_off, _off + _cnt)
        _off += _cnt

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
        section_matches: dict[str, int] = defaultdict(int)
        section_folios: dict[str, int] = defaultdict(int)
        for fn in folio_offsets:
            sec, _ = classify_folio(fn)
            section_folios[sec] += 1
        for m in matches_12:
            pos = m["position"]
            for fn, (start, end) in folio_offsets.items():
                if start <= pos < end:
                    sec, _ = classify_folio(fn)
                    section_matches[sec] += 1
                    break

        print(f"\n  Cycle match distribution by section (all {len(matches_12)}):")
        print(f"    {'section':<16}  {'matches':>7}  {'folios':>6}  {'per folio':>9}")
        for sec in sorted(section_matches.keys()):
            n = section_matches[sec]
            f = section_folios[sec]
            print(f"    {sec:<16}  {n:>7}  {f:>6}  {n/f:>9.1f}")

    # Phase 3: 7-glyph bootstrap core
    print(f"\nPhase 3 — 7-glyph bootstrap core search:")
    core_matches = find_cycle_in_stream(glyphs, BOOTSTRAP_CORE, max_mismatches=args.max_mismatches)
    exact_core = sum(1 for m in core_matches if m["mismatches"] == 0)
    near_core = sum(1 for m in core_matches if m["mismatches"] > 0)
    print(f"  Exact matches: {exact_core}")
    print(f"  Near matches:  {near_core}")

    print(f"\n  Bootstrap core link probabilities (vs dominant matrix):")
    for i in range(len(BOOTSTRAP_CORE)):
        g_from = BOOTSTRAP_CORE[i]
        g_to = BOOTSTRAP_CORE[(i + 1) % len(BOOTSTRAP_CORE)]
        prob = matrix.get(g_from, {}).get(g_to, 0.0)
        dominant_target = max(matrix.get(g_from, {'?': 0}).items(), key=lambda x: x[1], default=('?', 0))
        flag = '' if prob > 0.1 else f'  ← suppressed (dominant: {dominant_target[0]} p={dominant_target[1]:.2f})'
        print(f"    {g_from:>4} → {g_to:>4}: p={prob:.4f}{flag}")

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

    # Phase 7: Section-level bigram matrices
    print(f"\nPhase 7 — Section-level bigram matrices:")
    section_glyphs: dict[str, list[str]] = defaultdict(list)
    for fn, (start, end) in folio_offsets.items():
        sec, _ = classify_folio(fn)
        section_glyphs[sec].extend(glyphs[start:end])

    section_matrices: dict[str, dict] = {}
    for sec in sorted(section_glyphs.keys()):
        sg = section_glyphs[sec]
        if not sg:
            continue
        sm = build_bigram_matrix(sg)
        section_matrices[sec] = sm
        sg_gap = spectral_gap(sm)
        print(f"\n  [{sec}] — {len(sg)} glyphs, spectral gap {sg_gap:.4f}")
        print(f"    {'link':<12}  {'section p':>9}  {'global p':>8}  {'Δ':>7}")
        for i in range(len(DOMINANT_CYCLE)):
            g_from = DOMINANT_CYCLE[i]
            g_to = DOMINANT_CYCLE[(i + 1) % len(DOMINANT_CYCLE)]
            sp = sm.get(g_from, {}).get(g_to, 0.0)
            gp = matrix.get(g_from, {}).get(g_to, 0.0)
            delta = sp - gp
            sign = '+' if delta >= 0 else ''
            print(f"    {g_from:>4} → {g_to:<4}  {sp:>9.4f}  {gp:>8.4f}  {sign}{delta:.4f}")

    # Phase 8: Per-folio cycle density ranking
    print(f"\nPhase 8 — Per-folio cycle density ranking (top 15):")
    folio_hits: dict[str, int] = defaultdict(int)
    for m in matches_12:
        pos = m["position"]
        for fn, (start, end) in folio_offsets.items():
            if start <= pos < end:
                folio_hits[fn] += 1
                break

    folio_densities = []
    for fn, (start, end) in folio_offsets.items():
        gc = end - start
        hits = folio_hits.get(fn, 0)
        sec, _ = classify_folio(fn)
        folio_densities.append((fn, hits, gc, hits / gc if gc else 0.0, sec))
    folio_densities.sort(key=lambda x: x[3], reverse=True)

    print(f"  {'folio':<8}  {'hits':>5}  {'glyphs':>6}  {'density':>9}  section")
    for fn, hits, gc, density, sec in folio_densities[:15]:
        print(f"  {fn:<8}  {hits:>5}  {gc:>6}  {density:>9.4f}  {sec}")

    # Phase 9: Biological section — actual dominant cycle
    print(f"\nPhase 9 — Biological section: actual dominant cycle:")
    bio_glyphs = section_glyphs.get('biological', [])
    bio_matrix = section_matrices.get('biological', {})
    bio_cycle = dominant_cycle_from_matrix(bio_matrix, length=len(DOMINANT_CYCLE))
    if bio_cycle:
        print(f"  Biological dominant cycle:")
        print(f"    {' → '.join(bio_cycle)} → ({bio_cycle[0]})")
        print(f"  Link probabilities (section p vs global p):")
        for i in range(len(bio_cycle)):
            g_from = bio_cycle[i]
            g_to = bio_cycle[(i + 1) % len(bio_cycle)]
            sp = bio_matrix.get(g_from, {}).get(g_to, 0.0)
            gp = matrix.get(g_from, {}).get(g_to, 0.0)
            sign = '+' if sp - gp >= 0 else ''
            print(f"    {g_from:>4} → {g_to:>4}: p={sp:.4f}  (global {gp:.4f}, Δ={sign}{sp-gp:.4f})")
        bio_self = find_cycle_in_stream(bio_glyphs, bio_cycle, max_mismatches=args.max_mismatches)
        bio_global = find_cycle_in_stream(bio_glyphs, DOMINANT_CYCLE, max_mismatches=args.max_mismatches)
        print(f"  Biological cycle in bio stream: {sum(1 for m in bio_self if m['mismatches']==0)} exact, "
              f"{sum(1 for m in bio_self if m['mismatches']>0)} near "
              f"({len(bio_self)/max(1,len(bio_glyphs))*1000:.2f}/1000 glyphs)")
        print(f"  Global cycle in bio stream:     {sum(1 for m in bio_global if m['mismatches']==0)} exact, "
              f"{sum(1 for m in bio_global if m['mismatches']>0)} near "
              f"({len(bio_global)/max(1,len(bio_glyphs))*1000:.2f}/1000 glyphs)")
    else:
        print(f"  No complete 11-cycle found in biological section.")

    # Phase 10: Balneological o→e feed analysis
    print(f"\nPhase 10 — Balneological o→e feed analysis:")
    balne_matrix = section_matrices.get('balneological', {})

    inbound_o = sorted(
        ((g, row.get('o', 0.0)) for g, row in balne_matrix.items() if row.get('o', 0.0) > 0.001),
        key=lambda x: x[1], reverse=True,
    )
    print(f"  Inbound to o (VINIT) in balneological vs global:")
    for g, p in inbound_o:
        gp = matrix.get(g, {}).get('o', 0.0)
        sign = '+' if p - gp >= 0 else ''
        print(f"    {g:>4} → o: p={p:.4f}  (global {gp:.4f}, Δ={sign}{p-gp:.4f})")

    print(f"\n  Per-folio o→e rate within balneological:")
    print(f"    {'folio':<8}  {'o→e':>5}  {'total o':>7}  {'rate':>7}  {'global balne rate':>17}")
    balne_glyphs = section_glyphs.get('balneological', [])
    balne_oe_global = balne_matrix.get('o', {}).get('e', 0.0)
    balne_folios = sorted(
        (fn for fn, (s, e) in folio_offsets.items() if classify_folio(fn)[0] == 'balneological')
    )
    for fn in balne_folios:
        start, end = folio_offsets[fn]
        fg = glyphs[start:end]
        o_total = fg.count('o')
        oe_count = sum(1 for i in range(len(fg) - 1) if fg[i] == 'o' and fg[i+1] == 'e')
        rate = oe_count / o_total if o_total else 0.0
        print(f"    {fn:<8}  {oe_count:>5}  {o_total:>7}  {rate:>7.4f}  {balne_oe_global:>17.4f}")

    # Phase 11: Within-section cycle density variance
    print(f"\nPhase 11 — Within-section cycle density variance:")
    buckets_def = [(0.0, 0.0, '=0'), (0.0, 0.01, '0–0.01'), (0.01, 0.02, '0.01–0.02'),
                   (0.02, 0.04, '0.02–0.04'), (0.04, 0.06, '0.04–0.06'), (0.06, 1.0, '0.06+')]
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        sec_fd = [(fn, hits, gc, d) for fn, hits, gc, d, s in folio_densities if s == sec]
        if not sec_fd:
            continue
        densities = [d for _, _, _, d in sec_fd]
        mean = sum(densities) / len(densities)
        std = (sum((d - mean) ** 2 for d in densities) / len(densities)) ** 0.5
        cov = std / mean if mean > 0 else 0.0
        nonzero = sum(1 for d in densities if d > 0)
        print(f"\n  [{sec}] {len(densities)} folios, {nonzero} with ≥1 match — "
              f"mean={mean:.4f}, std={std:.4f}, CoV={cov:.2f}")
        print(f"  Top 5:")
        for fn, hits, gc, density in sec_fd[:5]:
            print(f"    {fn:<8}  {density:.4f}  ({hits} hits / {gc} glyphs)")
        print(f"  Density distribution:")
        for lo, hi, label in buckets_def:
            if lo == hi == 0.0:
                count = sum(1 for d in densities if d == 0.0)
            else:
                count = sum(1 for d in densities if lo < d <= hi)
            bar = '█' * min(count, 40)
            print(f"    {label:>10}: {bar} ({count})")

    # Phase 12: Biological — what beats each suppressed cycle link
    print(f"\nPhase 12 — Biological: what beats each suppressed cycle link:")
    bio_m = section_matrices.get('biological', {})
    for i in range(len(DOMINANT_CYCLE)):
        g_from = DOMINANT_CYCLE[i]
        g_to = DOMINANT_CYCLE[(i + 1) % len(DOMINANT_CYCLE)]
        cycle_p = bio_m.get(g_from, {}).get(g_to, 0.0)
        top3 = sorted(bio_m.get(g_from, {}).items(), key=lambda x: x[1], reverse=True)[:3]
        top3_str = ', '.join(f"{g}({p:.3f})" for g, p in top3)
        winner, won_p = top3[0] if top3 else ('?', 0.0)
        tag = '  ✓ holds' if winner == g_to else f'  ← beaten by {winner} ({won_p:.3f})'
        print(f"  {g_from:>4} → {g_to:>4}: p={cycle_p:.4f}  [{top3_str}]{tag}")

    # Phase 13: Balneological — full o-row cross-section + f75v anatomy
    print(f"\nPhase 13 — Balneological o-row cross-section comparison:")
    sec_order = ['balneological', 'botanical', 'cosmological', 'biological']
    o_targets = sorted({
        g for sec in sec_order
        for g, p in section_matrices.get(sec, {}).get('o', {}).items()
        if p > 0.005
    })
    hdr = '  '.join(f"{s[:5]:>7}" for s in sec_order)
    print(f"  {'o→':>4}  {hdr}  {'global':>7}")
    for target in o_targets:
        vals = [section_matrices.get(sec, {}).get('o', {}).get(target, 0.0) for sec in sec_order]
        gp = matrix.get('o', {}).get(target, 0.0)
        print(f"  o→{target:<4}  {'  '.join(f'{v:>7.4f}' for v in vals)}  {gp:>7.4f}")

    fn75 = 'f75v'
    if fn75 in folio_offsets:
        s75, e75 = folio_offsets[fn75]
        fg75 = glyphs[s75:e75]
        f75_m = build_bigram_matrix(fg75)
        balne_o = section_matrices.get('balneological', {}).get('o', {})
        print(f"\n  f75v o→X vs balneological (outlier folio, o→e rate 0.46 vs section 0.76):")
        print(f"    {'':>4}  {'f75v':>7}  {'balne':>7}  {'Δ':>7}")
        all_ot = sorted({*f75_m.get('o', {}), *balne_o})
        for t in all_ot:
            fp = f75_m.get('o', {}).get(t, 0.0)
            bp = balne_o.get(t, 0.0)
            if max(fp, bp) < 0.005:
                continue
            sign = '+' if fp - bp >= 0 else ''
            print(f"    o→{t:<4}  {fp:>7.4f}  {bp:>7.4f}  {sign}{fp-bp:.4f}")
        f75_cnt = Counter(fg75)
        balne_cnt = Counter(section_glyphs.get('balneological', []))
        balne_tot = len(section_glyphs.get('balneological', []))
        print(f"\n  f75v glyph proportions vs balneological:")
        print(f"    {'glyph':>5}  {'f75v%':>6}  {'balne%':>7}")
        for g in sorted(ALL_GLYPHS, key=lambda x: -f75_cnt.get(x, 0)):
            fp2 = f75_cnt.get(g, 0) / len(fg75) if fg75 else 0.0
            bp2 = balne_cnt.get(g, 0) / balne_tot if balne_tot else 0.0
            if max(fp2, bp2) < 0.01:
                continue
            print(f"    {g:>5}  {fp2:>6.3f}  {bp2:>7.3f}")

    # Phase 14: Botanical zero-match folio geography
    print(f"\nPhase 14 — Botanical zero-match folio geography:")

    def _folio_key(fn: str) -> tuple:
        m = re.match(r'f(\d+)(.*)', fn)
        return (int(m.group(1)), m.group(2)) if m else (999, fn)

    def _density_sym(d: float) -> str:
        if d == 0.0: return 'Z'
        if d <= 0.01: return '·'
        if d <= 0.02: return '○'
        if d <= 0.04: return '●'
        return '◉'

    bot_by_num = sorted(
        [(fn, hits, gc, d) for fn, hits, gc, d, s in folio_densities if s == 'botanical'],
        key=lambda x: _folio_key(x[0]),
    )
    zeros = [(fn, gc) for fn, hits, gc, d in bot_by_num if hits == 0]
    zero_nums = [_folio_key(fn)[0] for fn, _ in zeros]
    nonzero_nums = [_folio_key(fn)[0] for fn, hits, gc, d in bot_by_num if hits > 0]

    print(f"  Zero-match folios ({len(zeros)}):")
    for fn, gc in zeros:
        print(f"    {fn:<8}  ({gc} glyphs)")
    print(f"\n  Zero folio numbers:    mean={sum(zero_nums)/len(zero_nums):.1f}, "
          f"range {min(zero_nums)}–{max(zero_nums)}")
    print(f"  Nonzero folio numbers: mean={sum(nonzero_nums)/len(nonzero_nums):.1f}, "
          f"range {min(nonzero_nums)}–{max(nonzero_nums)}")

    line = ''.join(_density_sym(d) for _, _, _, d in bot_by_num)
    print(f"\n  Density map (folio order): Z=0  ·=0–0.01  ○=0.01–0.02  ●=0.02–0.04  ◉=0.04+")
    for i in range(0, len(line), 30):
        chunk = bot_by_num[i:i+30]
        print(f"    {chunk[0][0]:<8} [{line[i:i+30]}] {chunk[-1][0]}")

    # Phase 15: Cycle phase entry analysis
    print(f"\nPhase 15 — Cycle phase entry analysis (preferred entry point per section):")
    cycle_index = {g: i for i, g in enumerate(DOMINANT_CYCLE)}
    section_phase: dict[str, Counter] = defaultdict(Counter)
    for m in matches_12:
        first = m["sequence"][0] if m["sequence"] else None
        if first and first in cycle_index:
            pos = m["position"]
            for fn, (start, end) in folio_offsets.items():
                if start <= pos < end:
                    sec, _ = classify_folio(fn)
                    section_phase[sec][cycle_index[first]] += 1
                    break

    glyph_hdr = '  '.join(f"{g:>4}" for g in DOMINANT_CYCLE)
    idx_hdr   = '  '.join(f"{i:>4}" for i in range(len(DOMINANT_CYCLE)))
    print(f"  {'':16}  {glyph_hdr}")
    print(f"  {'':16}  {idx_hdr}")
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        counts = section_phase.get(sec, Counter())
        total = sum(counts.values())
        if not total:
            continue
        dom = max(range(len(DOMINANT_CYCLE)), key=lambda i: counts.get(i, 0))
        row = '  '.join(f"{counts.get(i, 0):>4}" for i in range(len(DOMINANT_CYCLE)))
        print(f"  {sec:<16}  {row}  dominant: ph{dom}={DOMINANT_CYCLE[dom]} "
              f"({counts[dom]}/{total}={counts[dom]/total*100:.0f}%)")

    # Phase 16: Recto/verso cycle density analysis
    print(f"\nPhase 16 — Recto/verso cycle density by section:")

    def _page_side(fn: str) -> str:
        m = re.search(r'[rv]', fn[1:])
        return ('recto' if m.group() == 'r' else 'verso') if m else 'other'

    side_section_hits: dict[tuple[str, str], int] = defaultdict(int)
    side_section_glyphs: dict[tuple[str, str], int] = defaultdict(int)
    side_section_folios: dict[tuple[str, str], int] = defaultdict(int)

    for fn, (start, end) in folio_offsets.items():
        sec, _ = classify_folio(fn)
        side = _page_side(fn)
        side_section_glyphs[(sec, side)] += end - start
        side_section_folios[(sec, side)] += 1
        side_section_hits[(sec, side)] += folio_hits.get(fn, 0)

    print(f"  {'section':<16}  {'side':<6}  {'folios':>6}  {'hits':>5}  {'glyphs':>7}  {'density':>8}  {'hits/folio':>10}")
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        for side in ['recto', 'verso']:
            key = (sec, side)
            f = side_section_folios.get(key, 0)
            h = side_section_hits.get(key, 0)
            g = side_section_glyphs.get(key, 0)
            if f == 0:
                continue
            density = h / g if g else 0.0
            hpf = h / f
            print(f"  {sec:<16}  {side:<6}  {f:>6}  {h:>5}  {g:>7}  {density:>8.4f}  {hpf:>10.2f}")
        print()

    # Phase 17: Pre-cycle trigger analysis
    print(f"Phase 17 — Pre-cycle trigger analysis (what precedes cycle entries):")
    pre_counts: dict[int, Counter] = {1: Counter(), 2: Counter(), 3: Counter()}
    exact_matches = [m for m in matches_12 if m['mismatches'] == 0]
    for m in exact_matches:
        pos = m['position']
        for lag in (1, 2, 3):
            if pos - lag >= 0:
                pre_counts[lag][glyphs[pos - lag]] += 1

    total_exact = len(exact_matches)
    print(f"  Based on {total_exact} exact cycle matches:")
    for lag in (1, 2, 3):
        top = pre_counts[lag].most_common(5)
        top_str = ', '.join(f"{g}({n}/{total_exact}={n/total_exact*100:.0f}%)" for g, n in top)
        print(f"  lag-{lag} (glyph at pos-{lag}): {top_str}")

    # Breakdown by section
    print(f"\n  Lag-1 trigger per section:")
    sec_pre: dict[str, Counter] = defaultdict(Counter)
    for m in exact_matches:
        pos = m['position']
        if pos >= 1:
            prev = glyphs[pos - 1]
            for fn, (start, end) in folio_offsets.items():
                if start <= pos < end:
                    sec, _ = classify_folio(fn)
                    sec_pre[sec][prev] += 1
                    break
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        top = sec_pre.get(sec, Counter()).most_common(4)
        top_str = ', '.join(f"{g}({n})" for g, n in top)
        print(f"    {sec:<16}: {top_str}")

    # Phase 18: TANCH (p) role — the non-cycle glyph
    print(f"\nPhase 18 — TANCH (p) role: the glyph absent from the dominant cycle:")
    print(f"  p→X probabilities by section:")
    p_targets = sorted({
        g for sec in ['balneological', 'botanical', 'cosmological', 'biological']
        for g, prob in section_matrices.get(sec, {}).get('p', {}).items()
        if prob > 0.005
    } | set(matrix.get('p', {}).keys()))
    hdr2 = '  '.join(f"{s[:5]:>7}" for s in ['balneological', 'botanical', 'cosmological', 'biological'])
    print(f"  {'p→':>4}  {hdr2}  {'global':>7}")
    for t in sorted(p_targets):
        vals = [section_matrices.get(sec, {}).get('p', {}).get(t, 0.0)
                for sec in ['balneological', 'botanical', 'cosmological', 'biological']]
        gp2 = matrix.get('p', {}).get(t, 0.0)
        if max(*vals, gp2) < 0.005:
            continue
        print(f"  p→{t:<4}  {'  '.join(f'{v:>7.4f}' for v in vals)}  {gp2:>7.4f}")

    # Does p form its own cycle?
    print(f"\n  Greedy cycle from p (global matrix):")
    p_cycle = dominant_cycle_from_matrix(matrix, length=len(DOMINANT_CYCLE))
    # Force start at p
    p_forced: list[str] = ['p']
    visited_p = {'p'}
    cur = 'p'
    p_probs: list[float] = []
    for _ in range(len(DOMINANT_CYCLE) - 1):
        row = matrix.get(cur, {})
        cands = sorted(((g, prob) for g, prob in row.items() if g not in visited_p),
                       key=lambda x: x[1], reverse=True)
        if not cands:
            break
        g, prob = cands[0]
        p_forced.append(g)
        visited_p.add(g)
        p_probs.append(prob)
        cur = g
    close_p = matrix.get(cur, {}).get('p', 0.0)
    p_probs.append(close_p)
    print(f"    {' → '.join(p_forced)} → (p)")
    print(f"    Link probabilities: {', '.join(f'{prob:.3f}' for prob in p_probs)}")
    if all(prob > 0 for prob in p_probs) and len(p_forced) == len(DOMINANT_CYCLE):
        p_geo = math.exp(sum(math.log(prob) for prob in p_probs) / len(p_probs))
        dom_probs = [matrix.get(DOMINANT_CYCLE[i], {}).get(DOMINANT_CYCLE[(i+1) % len(DOMINANT_CYCLE)], 0.0)
                     for i in range(len(DOMINANT_CYCLE))]
        dom_geo = math.exp(sum(math.log(p) for p in dom_probs if p > 0) / len(dom_probs))
        print(f"    Geometric mean: {p_geo:.4f}  (dominant cycle: {dom_geo:.4f})")
        p_matches = find_cycle_in_stream(glyphs, p_forced, max_mismatches=args.max_mismatches)
        p_exact = sum(1 for m in p_matches if m['mismatches'] == 0)
        print(f"    Corpus matches: {p_exact} exact, {len(p_matches)-p_exact} near "
              f"({len(p_matches)/max(1,len(glyphs))*1000:.2f}/1000 glyphs)")
    else:
        print(f"    Cycle does not close back to p (close_p={close_p:.4f})")

    # Phase 19: Biological Frobenius short-circuit — ch→o→? path
    print(f"\nPhase 19 — Biological Frobenius short-circuit: ch→o→? path:")
    bio_g = section_glyphs.get('biological', [])
    bio_m2 = section_matrices.get('biological', {})

    # Find all ch→o transitions in biological
    cho_positions = [i for i in range(len(bio_g) - 1) if bio_g[i] == 'ch' and bio_g[i+1] == 'o']
    print(f"  ch→o occurrences in biological: {len(cho_positions)}")

    # What follows o after ch→o (trigram ch→o→?)
    after_cho: Counter = Counter()
    for pos in cho_positions:
        if pos + 2 < len(bio_g):
            after_cho[bio_g[pos + 2]] += 1
    print(f"  ch→o→? distribution:")
    for g, n in after_cho.most_common():
        gp_oe = bio_m2.get('o', {}).get(g, 0.0)
        print(f"    ch→o→{g:<4}: {n:>3}  ({n/len(cho_positions)*100:.0f}%)  "
              f"vs unconditional o→{g}: {gp_oe:.3f}")

    # Does ch→o→e restart the cycle? Compare ch→o→e frequency in bio vs global
    cho_e_bio = after_cho.get('e', 0)
    print(f"\n  ch→o→e (cycle restart): {cho_e_bio}/{len(cho_positions)} "
          f"= {cho_e_bio/max(1,len(cho_positions))*100:.0f}% of ch→o transitions")
    # Global ch→o→e
    cho_global = [i for i in range(len(glyphs) - 2) if glyphs[i] == 'ch' and glyphs[i+1] == 'o']
    cho_e_global = sum(1 for i in cho_global if glyphs[i+2] == 'e')
    print(f"  ch→o→e (global):        {cho_e_global}/{len(cho_global)} "
          f"= {cho_e_global/max(1,len(cho_global))*100:.0f}% of ch→o transitions")

    # Longest ch→o chain before hitting e or dead end in biological
    print(f"\n  ch→o runs in biological (consecutive ch→o before breaking to non-o):")
    run_lengths: Counter = Counter()
    i = 0
    while i < len(bio_g) - 1:
        if bio_g[i] == 'ch' and bio_g[i+1] == 'o':
            run = 1
            j = i + 1
            while j < len(bio_g) - 1 and bio_g[j] == 'o' and j + 1 < len(bio_g):
                if bio_g[j+1] == 'ch':
                    j += 1
                    if j < len(bio_g) - 1 and bio_g[j+1] == 'o':
                        run += 1
                        j += 1
                    else:
                        break
                else:
                    break
            run_lengths[run] += 1
            i = j
        else:
            i += 1
    for length, count in sorted(run_lengths.items()):
        print(f"    run length {length}: {count}×")

    clen = len(DOMINANT_CYCLE)

    # Phase 20: Expected vs observed exact hit rates per section
    print(f"\nPhase 20 — Expected vs observed exact cycle hit rates:")
    print(f"  Expected = freq(o) × ∏ section link probabilities × 1000")
    sec_exact_counts: dict[str, int] = defaultdict(int)
    for m in matches_12:
        if m['mismatches'] == 0:
            pos = m['position']
            for fn, (start, end) in folio_offsets.items():
                if start <= pos < end:
                    sec, _ = classify_folio(fn)
                    sec_exact_counts[sec] += 1
                    break
    print(f"  {'section':<16}  {'freq(o)':>7}  {'∏links':>10}  {'exp/1k':>8}  {'obs/1k':>8}  {'ratio':>6}")
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        sg = section_glyphs.get(sec, [])
        sm = section_matrices.get(sec, {})
        if not sg:
            continue
        freq_o = sg.count('o') / len(sg)
        lps = [sm.get(DOMINANT_CYCLE[i], {}).get(DOMINANT_CYCLE[(i+1) % clen], 0.0)
               for i in range(clen)]
        p_cycle = math.prod(lps) if all(p > 0 for p in lps) else 0.0
        expected = freq_o * p_cycle * 1000
        observed = sec_exact_counts.get(sec, 0) / len(sg) * 1000
        ratio = observed / expected if expected > 0 else float('inf')
        print(f"  {sec:<16}  {freq_o:>7.4f}  {p_cycle:>10.8f}  {expected:>8.4f}  {observed:>8.4f}  {ratio:>6.2f}×")

    # Phase 21: Cycle chain length distribution
    print(f"\nPhase 21 — Cycle chain length distribution:")
    exact_pos_set = {m['position'] for m in matches_12 if m['mismatches'] == 0}
    exact_pos_sorted = sorted(exact_pos_set)
    chain_counts: Counter = Counter()
    visited_c: set = set()
    for pos in exact_pos_sorted:
        if pos in visited_c:
            continue
        depth = 1
        cur = pos
        while cur + clen in exact_pos_set:
            cur += clen
            depth += 1
            visited_c.add(cur)
        chain_counts[depth] += 1
        visited_c.add(pos)
    total_chains = sum(chain_counts.values())
    print(f"  {total_chains} chains, {len(exact_pos_set)} exact matches total")
    print(f"  {'depth':>6}  {'chains':>7}  {'% chains':>9}  {'glyphs':>7}")
    for depth in sorted(chain_counts.keys()):
        n = chain_counts[depth]
        print(f"  {depth:>6}  {n:>7}  {n/total_chains*100:>9.1f}%  {depth*clen:>7}")
    mean_depth = sum(d * n for d, n in chain_counts.items()) / total_chains
    print(f"  Mean chain depth: {mean_depth:.2f} cycles  "
          f"(max: {max(chain_counts.keys())} cycles = {max(chain_counts.keys())*clen} glyphs)")

    # Phase 22: Per-section information entropy
    print(f"\nPhase 22 — Per-section information entropy:")

    def _row_entropy(row: dict[str, float]) -> float:
        return -sum(p * math.log2(p) for p in row.values() if p > 0)

    max_H = math.log2(len(PRIMITIVES))
    print(f"  Max possible entropy (12 uniform): {max_H:.4f} bits")
    print(f"  {'section':<16}  {'unigram H':>10}  {'transition H':>13}  {'spectral gap':>13}  {'H/gap':>7}")
    for sec in ['botanical', 'cosmological', 'balneological', 'biological']:
        sg = section_glyphs.get(sec, [])
        sm = section_matrices.get(sec, {})
        if not sg or not sm:
            continue
        freq = Counter(sg)
        total = len(sg)
        uni_H = -sum((freq[g]/total) * math.log2(freq[g]/total) for g in freq if freq[g] > 0)
        trans_H = sum((freq[g] / total) * _row_entropy(sm[g]) for g in freq if g in sm and sm[g])
        sg_gap = spectral_gap(sm)
        print(f"  {sec:<16}  {uni_H:>10.4f}  {trans_H:>13.4f}  {sg_gap:>13.4f}  {trans_H/sg_gap:>7.2f}")

    # Phase 23: Structural folio misclassification
    print(f"\nPhase 23 — Structural folio misclassification (unigram JS divergence):")

    def _js(fg_counts: Counter, sec_counts: Counter) -> float:
        vocab = ALL_GLYPHS
        np_ = sum(fg_counts.values()) + len(vocab)
        nq_ = sum(sec_counts.values()) + len(vocab)
        p_ = {g: (fg_counts.get(g, 0) + 1) / np_ for g in vocab}
        q_ = {g: (sec_counts.get(g, 0) + 1) / nq_ for g in vocab}
        m_ = {g: 0.5 * (p_[g] + q_[g]) for g in vocab}
        kl_pm = sum(p_[g] * math.log2(p_[g] / m_[g]) for g in vocab)
        kl_qm = sum(q_[g] * math.log2(q_[g] / m_[g]) for g in vocab)
        return 0.5 * kl_pm + 0.5 * kl_qm

    sec_glyph_counts = {sec: Counter(sg) for sec, sg in section_glyphs.items() if sg}
    sec_names_p23 = ['botanical', 'cosmological', 'balneological', 'biological']
    misclassified = []
    for fn, (start, end) in folio_offsets.items():
        fg = glyphs[start:end]
        if len(fg) < 30:
            continue
        fg_cnt = Counter(fg)
        native, _ = classify_folio(fn)
        if native not in sec_glyph_counts:
            continue
        divs = {sec: _js(fg_cnt, sec_glyph_counts[sec]) for sec in sec_names_p23}
        closest = min(divs, key=divs.get)
        if closest != native:
            misclassified.append((fn, native, closest, divs[native], divs[closest]))
    misclassified.sort(key=lambda x: x[4] - x[3])
    print(f"  {len(misclassified)} folios structurally closer to a non-native section:")
    print(f"  {'folio':<8}  {'native':<16}  {'closest':<16}  {'native JS':>9}  {'closest JS':>10}  {'gap':>7}")
    for fn, native, closest, ndjs, cdjs in misclassified[:20]:
        print(f"  {fn:<8}  {native:<16}  {closest:<16}  {ndjs:>9.4f}  {cdjs:>10.4f}  {ndjs-cdjs:>7.4f}")

    # Phase 24: All cycle-body initiators (X → e → a → d → s → t → k → r → y → ch → sh)
    print(f"\nPhase 24 — All cycle-body initiators (X → e → … → sh):")
    cycle_body = list(DOMINANT_CYCLE[1:])
    body_len = len(cycle_body)
    initiator_counts: Counter = Counter()
    for i in range(1, len(glyphs) - body_len + 1):
        if glyphs[i:i + body_len] == cycle_body:
            initiator_counts[glyphs[i - 1]] += 1
    total_body = sum(initiator_counts.values())
    print(f"  {total_body} cycle-body occurrences with known predecessor:")
    print(f"  {'glyph':>6}  {'count':>6}  {'%':>6}  mnemonic")
    for g, count in initiator_counts.most_common():
        mn = PRIMITIVES.get(g, {}).get('mnemonic', '?')
        print(f"  {g:>6}  {count:>6}  {count/total_body*100:>6.1f}%  {mn}")

    # Phase 25: Bootstrap core maximum partial match
    print(f"\nPhase 25 — Bootstrap core maximum partial match:")
    bc_max_run = 0
    bc_max_pos = 0
    bc_max_phase = 0
    bc_run_dist: Counter = Counter()
    for i in range(len(glyphs)):
        for phase in range(len(BOOTSTRAP_CORE)):
            run = 0
            for j in range(len(BOOTSTRAP_CORE)):
                if i + j >= len(glyphs):
                    break
                if glyphs[i + j] == BOOTSTRAP_CORE[(phase + j) % len(BOOTSTRAP_CORE)]:
                    run += 1
                else:
                    break
            if run > bc_max_run:
                bc_max_run, bc_max_pos, bc_max_phase = run, i, phase
            if run >= 2:
                bc_run_dist[run] += 1
    print(f"  Bootstrap core: {' → '.join(BOOTSTRAP_CORE)}")
    print(f"  Maximum partial match: {bc_max_run} consecutive glyphs")
    if bc_max_run > 0:
        ctx_start = max(0, bc_max_pos - 2)
        ctx_end = min(len(glyphs), bc_max_pos + bc_max_run + 2)
        print(f"  Position {bc_max_pos}, phase offset {bc_max_phase} ({BOOTSTRAP_CORE[bc_max_phase]})")
        print(f"  Context: {' '.join(glyphs[ctx_start:ctx_end])}")
    if bc_run_dist:
        print(f"  Partial match distribution (≥2 consecutive):")
        for length in sorted(bc_run_dist.keys(), reverse=True):
            print(f"    length {length}: {bc_run_dist[length]}×")
    else:
        print(f"  No partial matches of length ≥2 found.")

    # Phase 26: Initiator continuation rates (o vs p)
    print(f"\nPhase 26 — Initiator continuation rates (o vs p):")
    p_seq = ['p'] + list(DOMINANT_CYCLE[1:])
    p_exact_matches = find_cycle_in_stream(glyphs, p_seq, max_mismatches=0)
    p_exact_pos = {m['position'] for m in p_exact_matches}

    o_continues = sum(1 for pos in exact_pos_set if pos + clen in exact_pos_set)
    p_to_o = sum(1 for pos in p_exact_pos if pos + clen in exact_pos_set)
    p_to_p = sum(1 for pos in p_exact_pos if pos + clen in p_exact_pos)

    print(f"  o-initiated exact: {len(exact_pos_set)}, chains into another o-cycle: "
          f"{o_continues} ({o_continues/max(1,len(exact_pos_set))*100:.1f}%)")
    print(f"  p-initiated exact: {len(p_exact_pos)}, chains into o-cycle at +{clen}: "
          f"{p_to_o} ({p_to_o/max(1,len(p_exact_pos))*100:.1f}%)")
    print(f"  p-initiated exact: chains into another p-cycle at +{clen}: "
          f"{p_to_p} ({p_to_p/max(1,len(p_exact_pos))*100:.1f}%)")

    # What comes after each initiator type?
    post_o: Counter = Counter()
    post_p_counter: Counter = Counter()
    for pos in exact_pos_set:
        nxt = pos + clen
        if nxt < len(glyphs):
            post_o[glyphs[nxt]] += 1
    for pos in p_exact_pos:
        nxt = pos + clen
        if nxt < len(glyphs):
            post_p_counter[glyphs[nxt]] += 1
    print(f"\n  Glyph at pos+{clen} after o-cycle: "
          + ', '.join(f"{g}({n})" for g, n in post_o.most_common(5)))
    print(f"  Glyph at pos+{clen} after p-cycle: "
          + ', '.join(f"{g}({n})" for g, n in post_p_counter.most_common(5)))

    # Chain-depth distribution
    print(f"\n  Chain-depth distribution (o-initiated exact):")
    depth_dist: Counter = Counter()
    for pos in exact_pos_sorted:
        if pos - clen not in exact_pos_set:
            depth = 1
            cur = pos
            while cur + clen in exact_pos_set:
                depth += 1
                cur += clen
            depth_dist[depth] += 1
    total_d = sum(depth_dist.values())
    for depth in sorted(depth_dist.keys()):
        n = depth_dist[depth]
        bar = '█' * n
        print(f"    depth {depth:>2} ({depth*clen:>3} glyphs): {bar} ({n}, {n/total_d*100:.0f}%)")

    print(f"\n=== SUMMARY ===")

    print(f"  Dominant 11-cycle exact matches: {exact_12}")
    print(f"  7-glyph bootstrap exact matches: {exact_core}")
    print(f"  Cross-folio closures:           {cross_folio_matches}")
    print(f"  Spectral gap:                   {gap:.6f}")
    print(f"  Longest cycle run:              {longest_run} glyphs")
    print()


if __name__ == "__main__":
    main()