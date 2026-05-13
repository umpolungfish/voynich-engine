#!/usr/bin/env python3
"""
Register Lifecycle Tracker — trace individual Tri-Phase registers through execution.

For each register in the Voynich Engine, this program tracks:
  1. Birth: which instruction/step activates it
  2. First opcode: what operation initialized it
  3. Lifecycle events: how many times it's referenced, when
  4. Death/fixation: when IFIX burns it to ROM
  5. Paradox history: when it enters Both state
  6. Lifespan: steps between first activation and fixation

Outputs:
  - Register lifecycle histogram (lifespan distribution)
  - Opcode→fixation latency (which opcodes lead to fastest IFIX)
  - Register "families" (registers born in the same instruction cluster)
  - Survival curve (Kaplan-Meier style: fraction of registers still active vs step)

Usage:
    python programs/register_lifecycle.py data/LSI_ivtff_0d.txt [--steps 100000] [--sample 1000]
"""

from __future__ import annotations
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voynich_engine import compile_corpus, UniversalEngine, PRIMITIVES

_REG_PATTERN = re.compile(r'%r(\d+)')
MNEMONIC_TO_GLYPH = {meta["mnemonic"]: glyph for glyph, meta in PRIMITIVES.items()}


class RegisterTrace:
    """Lifecycle trace for a single register."""
    __slots__ = ("reg_id", "birth_step", "birth_opcode", "first_folio",
                 "references", "fix_step", "paradox_steps", "death_step")

    def __init__(self, reg_id: int, step: int, opcode: str, folio: str):
        self.reg_id = reg_id
        self.birth_step = step
        self.birth_opcode = opcode
        self.first_folio = folio
        self.references: list[int] = [step]
        self.fix_step: int | None = None
        self.paradox_steps: list[int] = []
        self.death_step: int | None = None

    @property
    def lifespan(self) -> int:
        end = self.fix_step or self.death_step or 0
        return end - self.birth_step

    @property
    def is_fixed(self) -> bool:
        return self.fix_step is not None

    @property
    def reference_count(self) -> int:
        return len(self.references)


def mnemonic_from_instruction(instr: str) -> str | None:
    """Extract the mnemonic from an instruction line."""
    for mnemonic in ["VINIT", "TANCH", "AFWD", "AREV", "CLINK", "ISCRIB",
                     "FSPLIT", "FFUSE", "EVALT", "EVALF", "ENGAGR", "IFIX"]:
        if mnemonic in instr:
            return mnemonic
    return None


def folio_for_instruction_index(index: int, result: dict) -> str:
    """Map a global instruction index back to its folio name."""
    cumulative = 0
    for folio_name in sorted(result["folios"].keys()):
        n_instr = len(result["folios"][folio_name]["instructions"])
        if index < cumulative + n_instr:
            return folio_name
        cumulative += n_instr
    return "unknown"


def trace_registers(result: dict, steps: int, sample_regs: set[int] | None = None) -> dict[int, RegisterTrace]:
    """
    Execute the engine while recording lifecycle events for each register.
    If sample_regs is given, only trace those registers (for performance).
    """
    engine = UniversalEngine.from_compilation(result)
    program = engine.program
    traces: dict[int, RegisterTrace] = {}

    for step_idx in range(steps):
        pc = step_idx % len(program)
        instr = program[pc]

        regs = [int(x) for x in _REG_PATTERN.findall(instr)]
        if not regs:
            continue

        mnemonic = mnemonic_from_instruction(instr)
        folio = folio_for_instruction_index(pc, result)
        opcode = mnemonic or "DATA"

        for r in regs:
            if sample_regs and r not in sample_regs:
                continue

            if r not in traces:
                traces[r] = RegisterTrace(r, step_idx, opcode, folio)
            else:
                traces[r].references.append(step_idx)

            if "IFIX" in instr and traces[r].fix_step is None:
                traces[r].fix_step = step_idx
            elif ("FSPLIT" in instr or "ENGAGR" in instr):
                traces[r].paradox_steps.append(step_idx)

    return traces

def compute_lifespan_distribution(traces: dict[int, RegisterTrace]) -> dict[int, int]:
    """Histogram of lifespans for fixed registers."""
    dist: Counter = Counter()
    for t in traces.values():
        if t.is_fixed:
            dist[t.lifespan] += 1
    return dict(dist)


def compute_opcode_fixation_latency(traces: dict[int, RegisterTrace]) -> dict[str, list[int]]:
    """For each birth opcode, collect fixation latencies."""
    latencies: dict[str, list[int]] = defaultdict(list)
    for t in traces.values():
        if t.is_fixed:
            latencies[t.birth_opcode].append(t.lifespan)
    return dict(latencies)


def compute_survival_curve(traces: dict[int, RegisterTrace], max_step: int, bins: int = 50) -> list[tuple[int, float]]:
    """Kaplan-Meier style survival curve: fraction of registers not yet fixed at each step bin."""
    if not traces:
        return []

    bin_size = max(1, max_step // bins)
    curve: list[tuple[int, float]] = []

    born_by_bin: dict[int, int] = defaultdict(int)
    fixed_by_bin: dict[int, int] = defaultdict(int)

    for t in traces.values():
        birth_bin = t.birth_step // bin_size
        born_by_bin[birth_bin] += 1
        if t.fix_step is not None:
            fix_bin = t.fix_step // bin_size
            fixed_by_bin[fix_bin] += 1

    alive = 0
    for b in range(bins + 1):
        alive += born_by_bin.get(b, 0)
        alive -= fixed_by_bin.get(b, 0)
        total_born = sum(born_by_bin.get(i, 0) for i in range(b + 1))
        frac = alive / max(1, total_born)
        curve.append((b * bin_size, frac))

    return curve


def compute_register_families(traces: dict[int, RegisterTrace], max_gap: int = 5) -> list[list[int]]:
    """
    Group registers into "families" — registers born within `max_gap` steps of each other.
    These correspond to instruction clusters (single folio lines or bootstrap loops).
    """
    if not traces:
        return []

    sorted_regs = sorted(traces.values(), key=lambda t: t.birth_step)
    families: list[list[int]] = []
    current_family = [sorted_regs[0].reg_id]
    last_birth = sorted_regs[0].birth_step

    for t in sorted_regs[1:]:
        if t.birth_step - last_birth <= max_gap:
            current_family.append(t.reg_id)
        else:
            families.append(current_family)
            current_family = [t.reg_id]
        last_birth = t.birth_step

    if current_family:
        families.append(current_family)

    return families


def main() -> None:
    parser = argparse.ArgumentParser(description="Register Lifecycle Tracker")
    parser.add_argument("transcription", help="Path to LSI_ivtff_0d.txt")
    parser.add_argument("--steps", type=int, default=100000, help="Execution steps")
    parser.add_argument("--sample", type=int, default=0,
                        help="Sample N registers (0 = trace all)")
    args = parser.parse_args()

    print("=== REGISTER LIFECYCLE TRACKER ===\n")

    print("Compiling corpus...")
    result = compile_corpus(args.transcription)
    print(f"  Folios: {result['folio_count']}")
    print(f"  Registers: {result['total_registers']}")
    print(f"  Instructions: {result['total_instructions']}\n")

    # Determine sample set
    sample_regs = None
    if args.sample > 0:
        rng = __import__("random").Random(42)
        sample_regs = set(rng.sample(range(result["total_registers"]),
                                     min(args.sample, result["total_registers"])))
        print(f"Sampling {len(sample_regs)} registers...\n")

    # Phase 1: Trace
    print(f"Phase 1 — Tracing register lifecycles ({args.steps} steps)...")
    traces = trace_registers(result, args.steps, sample_regs)
    print(f"  Traced {len(traces)} registers.\n")

    # Phase 2: Lifespan distribution
    print("Phase 2 — Lifespan distribution (fixed registers):")
    lifespan_dist = compute_lifespan_distribution(traces)
    if lifespan_dist:
        sorted_lifespans = sorted(lifespan_dist.items())
        lifespans = [ls for ls, _ in sorted_lifespans]
        counts = [c for _, c in sorted_lifespans]
        total_fixed = sum(counts)

        print(f"  Total fixed registers: {total_fixed}")
        print(f"  Min lifespan: {min(lifespans)} steps")
        print(f"  Max lifespan: {max(lifespans)} steps")
        import statistics
        mean_ls = sum(ls * c for ls, c in sorted_lifespans) / total_fixed
        print(f"  Mean lifespan: {mean_ls:.1f} steps")
        if len(lifespans) > 1:
            median_ls = statistics.median(lifespans)
            print(f"  Median lifespan: {median_ls:.0f} steps")

        # Show distribution buckets
        bucket_size = max(1, (max(lifespans) - min(lifespans)) // 10)
        buckets: dict[int, int] = defaultdict(int)
        for ls, count in sorted_lifespans:
            bucket_key = (ls // bucket_size) * bucket_size
            buckets[bucket_key] += count

        print(f"\n  Lifespan histogram (bucket size={bucket_size}):")
        for bk in sorted(buckets.keys()):
            bar = '█' * min(50, buckets[bk])
            print(f"    {bk:>6d}-{bk+bucket_size:<6d} : {buckets[bk]:>5d} {bar}")

    # Phase 3: Opcode → fixation latency
    print(f"\nPhase 3 — Birth opcode → fixation latency:")
    latencies = compute_opcode_fixation_latency(traces)
    if latencies:
        print(f"  {'Birth Opcode':<14} {'N Fixed':>8} {'Mean Latency':>13} {'Min':>6} {'Max':>6}")
        print(f"  {'-'*14} {'-'*8} {'-'*13} {'-'*6} {'-'*6}")
        for opcode in sorted(latencies.keys()):
            lats = latencies[opcode]
            mean_lat = sum(lats) / len(lats)
            print(f"  {opcode:<14} {len(lats):>8} {mean_lat:>13.1f} {min(lats):>6} {max(lats):>6}")

    # Phase 4: Survival curve
    print(f"\nPhase 4 — Register survival curve:")
    curve = compute_survival_curve(traces, args.steps, bins=20)
    if curve:
        for step, frac in curve:
            bar_len = int(frac * 40)
            bar = '█' * bar_len + '░' * (40 - bar_len)
            print(f"    Step {step:>7d}: {frac:>6.2%} |{bar}|")

    # Phase 5: Register families
    print(f"\nPhase 5 — Register families (birth gap ≤ 5 steps):")
    families = compute_register_families(traces)
    if families:
        family_sizes = [len(f) for f in families]
        print(f"  Total families: {len(families)}")
        print(f"  Family size: min={min(family_sizes)}, max={max(family_sizes)}, "
              f"mean={sum(family_sizes)/len(family_sizes):.1f}")

        largest = max(families, key=len)
        if len(largest) <= 20:
            print(f"  Largest family: {largest}")
        else:
            print(f"  Largest family (first 20): {largest[:20]}...")

        # Size distribution
        size_dist = Counter(family_sizes)
        print(f"\n  Family size distribution:")
        for size in sorted(size_dist.keys()):
            bar = '█' * min(50, size_dist[size])
            print(f"    Size {size:>4d}: {size_dist[size]:>5d} {bar}")

    # Phase 6: Paradox statistics
    print(f"\nPhase 6 — Paradox engagement statistics:")
    paradox_regs = [t for t in traces.values() if t.paradox_steps]
    if paradox_regs:
        print(f"  Registers with paradox engagement: {len(paradox_regs)} / {len(traces)}")
        multi_paradox = [t for t in paradox_regs if len(t.paradox_steps) > 1]
        print(f"  Registers with multiple engagements: {len(multi_paradox)}")
        if multi_paradox:
            max_engagements = max(len(t.paradox_steps) for t in paradox_regs)
            print(f"  Max engagements for single register: {max_engagements}")
    else:
        print(f"  No paradox engagements detected in traced registers.")

    print(f"\n=== SUMMARY ===")
    fixed_count = sum(1 for t in traces.values() if t.is_fixed)
    paradox_count = sum(1 for t in traces.values() if t.paradox_steps)
    print(f"  Traced: {len(traces)}, Fixed: {fixed_count}, Paradox: {paradox_count}")
    print(f"  Fixation rate: {fixed_count/max(1,len(traces)):.2%}")
    print()


if __name__ == "__main__":
    main()