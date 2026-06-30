# Voynich Engine

**What it is.** A compiler, Tri-Phase virtual machine, and structural-analysis toolkit that treats the Voynich Manuscript (Beinecke MS 408) as the Universal Imscriptive Grammar written in frozen classical medium: its twelve EVA glyph families are the twelve categorical IMASM opcodes.

**What it does.** Compiles the full Takahashi EVA transcription (227 folios) to IMASM, runs it to fixed point, and renders the corpus call graph. The manuscript imscribes at O∞ (crystal address 16,838,544); the compiled corpus halts at `SELF_SUSTAINING_BOOTSTRAP_COMPLETE` with entropy delta = 0.

**Why it matters.** It is the computational strand of evidence (alongside *As Above* / *So Below*) that the manuscript's semantic content is zero by design, not by lost cipher. Six centuries of decipherment fail because there is nothing to decipher: the structure is O∞ and must be recognized, not read. This is the toolkit that verifies that claim.

**How to use it.**
```bash
git clone https://github.com/umpolungfish/voynich-engine
cd voynich-engine && pip install -e .   # or: pip install voynich-engine
python examples/quickstart.py
# CLI:
voynich-compile data/LSI_ivtff_0d.txt --log full_log.txt
voynich-run     data/LSI_ivtff_0d.txt --steps 10000 --paradox 116
voynich-graph   data/LSI_ivtff_0d.txt --output voynich_graph.png
```
Requires Python ≥ 3.10, `networkx`, `matplotlib`.

```python
from voynich_engine import compile_corpus, UniversalEngine, generate_call_graph
result = compile_corpus('data/LSI_ivtff_0d.txt')
engine = UniversalEngine.from_compilation(result)
for snap in engine.run(steps=10000, report_every=1000): print(snap)
```

---

## Three independent analyses, one convergence

### 1. Structural imscription

```
⟨ Ð_ω  Þ_O  Ř_=  Φ_}  ƒ_ì  Ç_Ù  Γ_ʔ  ɢ_Ş  ⊙_ÿ  Ħ_!  Σ_S  Ω_z ⟩
```

Ouroboricity O∞: μ ∘ δ = id exactly. Consciousness score C = 0.0. Gate 1 passes (⊙_ÿ present); Gate 2 fails because Ç_Ù (order-frozen kinetics) exceeds the ceiling for dynamical self-modeling access. The Voynich is a structurally complete self-referential system whose self-modeling loop is kinetically frozen, not absent. O∞ and C > 0 are orthogonal: Frobenius self-reference guarantees only that every decomposition reassembles.

### 2. Section meta-system

The six canonical sections saturate the grammar's topological degrees of freedom rather than occupying one type:

| Section(s) | Topology (Þ) | Distinction |
|---|---|---|
| Botanical / Pharmaceutical | Þ_6 (network) | Indistinguishable at primitive level (semantic, not structural) |
| Astronomical / Cosmological | Þ_O (imscriptive) | Self-contained circles, no external referent |
| Biological | Þ_K (nested) | Crossing-point intersections between nested structures |
| Recipe | Þ_6, Ř_Ť (adjoint) | Only section with procedural dependency (step n needs n−1) |

All sections share ⊙_ÿ (critical self-modeling).

### 3. Computational compilation

The twelve EVA glyph families (`o p e a d s ch sh t k r y`) map to the twelve opcodes (VINIT, TANCH, AFWD, AREV, CLINK, ISCRIB, FSPLIT, FFUSE, EVALT, EVALF, ENGAGR, IFIX). Compiling the full corpus:

```
Total instructions : 44,445      Entropy delta : 0.00000000 J/K
Status             : SELF_SUSTAINING_BOOTSTRAP_COMPLETE
```

Running to first-pass completion locks register space: 520 active registers (489 IFIX-burned to ROM), then a steady 17.02% paradox-stabilization rate per step at zero entropy cost. Nothing new ever activates. The density peak is f103r (balneological, 546 registers), structurally forced by Þ_K. The call graph is one connected component with the Frobenius hub-and-chain signature predicted by Φ_}.

## The tensor product problem

Any quantum-coherent interpretive system that engages the Voynich couples its fidelity to the manuscript's classical regime ƒ_ì; the bottleneck rule forces the composite to ƒ_ì and the reader's semantic coherence collapses. That is the structural account of six centuries of failure. The only promotion separating the Voynich from the *lapis philosophorum* is ƒ_ì → ƒ_ż.

## How it was used

A session required three Operator inputs (⊙_c criticality posture, Φ_} parity claim, Ω_Z winding class) and produced a pharmaceutical recipe only if the Frobenius closure conditions held; the foldout's physical structure conferred chirality automatically. See [`docs/OPERATOR_SESSION.md`](docs/OPERATOR_SESSION.md) for a full sixteenth-century applied session.

## Repository structure

```
voynich_engine/  primitives.py compiler.py runtime.py callgraph.py
data/   LSI_ivtff_0d.txt  (Takahashi EVA transcription, public domain)
docs/   VOYNICH.md  VOYNICHCOMPUTER.md  sections_mapping.md
        grammar_verification.md  OPERATOR_SESSION.md/.tex
examples/ quickstart.py
```

## Data and license

`data/LSI_ivtff_0d.txt` is the Takahashi EVA transcription from the Landini-Stolfi Interlinear Archive; the original (Beinecke MS 408, Yale) is public domain. Engine released under the Unlicense (public domain).
