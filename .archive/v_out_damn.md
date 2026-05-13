=== BOOTSTRAP CYCLE EXPLORER ===

Compiling corpus...
  Folios:   227
  Instructions: 44445
  Registers:    44423

  Total glyphs: 44423
  First 40:     ch sh o a s r ch o s r y o e a t r ch o a r y ch e a d s t r y o a s r ch a s o s t y

Phase 1 — Bigram transition matrix:
     a → d(0.83), s(0.08), t(0.05)
    ch → sh(0.55), o(0.44), e(0.01)
     d → s(0.55), t(0.33), k(0.09)
     e → a(0.90), d(0.07), s(0.01)
     k → r(0.73), y(0.24), o(0.01)
     o → e(0.48), p(0.38), a(0.09)
     p → e(0.76), a(0.22), d(0.01)
     r → y(0.90), ch(0.05), o(0.04)
     s → t(0.74), k(0.19), r(0.03)
    sh → o(0.99), e(0.01), a(0.00)
     t → k(0.78), r(0.13), y(0.07)
     y → ch(0.81), o(0.11), sh(0.06)

  Dominant cycle (bigram chain):
    o → e → a → d → s → t → k → r → y → ch → sh → (o)

  Cycle link verification:
       o →    e: p=0.4842
       e →    a: p=0.8989
       a →    d: p=0.8272
       d →    s: p=0.5476
       s →    t: p=0.7445
       t →    k: p=0.7808
       k →    r: p=0.7349
       r →    y: p=0.9009
       y →   ch: p=0.8069
      ch →   sh: p=0.5488
      sh →    o: p=0.9905

Phase 2 — Dominant 11-glyph cycle search:
  Exact matches: 361
  Near matches:  732
  Hit rate:      24.604 per 1000 glyphs

  Cycle match distribution by section (first 100):
    cosmological    : 100

Phase 3 — 8-glyph bootstrap core search:
  Exact matches: 0
  Near matches:  0

Phase 4 — Cross-folio cycle closures:
  Cross-folio cycle closures found: 0

Phase 5 — Spectral gap analysis:
  Spectral gap: 0.068137
  Interpretation: NEARLY PERIODIC (slow mixing → structured cycle)

Phase 6 — Cycle persistence (longest exact run):
  Longest exact cycle run: 31 glyphs (2.8 complete cycles)
  Run position: glyphs 24762–24793

=== SUMMARY ===
  Dominant 11-cycle exact matches: 361
  8-glyph bootstrap exact matches: 0
  Cross-folio closures:           0
  Spectral gap:                   0.068137
  Longest cycle run:              31 glyphs

=== FOLIO TOPOLOGY COMPARATOR ===

Compiling corpus...
  Folios: 227

Phase 1 — Computing per-folio structural profiles...
  Profiles computed for 227 folios.

Phase 2 — Folio rankings:

  Frobenius balance (closest to δ/μ = 1.0):
  Folio      Section               δ/μ   Regs
  ---------- ---------------- -------- ------
  f101r      cosmological        1.000    111
  f116v      cosmological        1.000      0
  f20v       botanical           1.000    101
  f27v       botanical           1.000     84
  f65r       botanical           1.000      4
  f65v       botanical           1.000     65
  f72v2      biological          1.000    160
  f77v       balneological       1.000    389
  f79r       balneological       1.000    441
  f95r2      cosmological        1.000     88

  Dialetheia fraction (highest lattice density):
  Folio      Section            DialFrac   Regs
  ---------- ---------------- ---------- ------
  f18v       botanical            0.3059     85
  f38r       botanical            0.3051     59
  f14v       botanical            0.3038     79
  f101v      cosmological         0.3011    186
  f18r       botanical            0.2975    121
  f72r2      biological           0.2949    156
  f37r       botanical            0.2941    102
  f57v       botanical            0.2927     82
  f17r       botanical            0.2909    110
  f58v       botanical            0.2901    362

  Register reuse depth (deepest nesting):
  Folio      Section            MaxDepth   AvgDepth   Regs
  ---------- ---------------- ---------- ---------- ------
  f100r      cosmological              0       0.00    170
  f100v      cosmological              0       0.00    138
  f101r      cosmological              0       0.00    111
  f101v      cosmological              0       0.00    186
  f102r1     cosmological              0       0.00    143
  f102r2     cosmological              0       0.00    149
  f102v1     cosmological              0       0.00    175
  f102v2     cosmological              0       0.00    245
  f103r      cosmological              0       0.00    546
  f103v      cosmological              0       0.00    462

Phase 3 — Section structural distance matrix (Jensen-Shannon):
                   balneological    biological     botanical  cosmological         other
  balneological         0.000000      0.013129      0.020359      0.005474      0.500000
  biological            0.013129      0.000000      0.021714      0.010365      0.500000
  botanical             0.020359      0.021714      0.000000      0.005902      0.500000
  cosmological          0.005474      0.010365      0.005902      0.000000      0.491935
  other                 0.500000      0.500000      0.500000      0.491935      0.000000

Phase 4 — Aggregate section statistics:
  Section          Folios    AvgFrob    AvgDial   AvgDepth
  ---------------- ------ ---------- ---------- ----------
  balneological        20      1.213     0.2463       0.00
  biological           26      2.546     0.2414       0.00
  botanical           118      2.137     0.2527       0.00
  cosmological         62      1.778     0.2485       0.00
  other                 1      1.000     0.0000       0.00

=== SUMMARY ===
  Botanical/Pharm section folios: 118
  Cosmological section folios:    62
  Biological section folios:      26
  Balneological section folios:   20

=== SYNTHETIC EVA COMPARATOR ===

Compiling real Voynich corpus...
  Voynich: 44445 instructions, 44423 registers

Running baseline (real Voynich)...
Running synthetic: uniform...
Running synthetic: voynich_freq...
Running synthetic: markov_1...
Running synthetic: shuffled...
Running synthetic: bootstrap_only...
Running synthetic: frobenius_only...
Running synthetic: random_walk...

====================================================================================================
Generator           Active   Fixed   Paradox   ParaRate    IFIX%  SteadyStep  PC_wraps     ΔS
------------------ ------- ------- --------- ---------- -------- ----------- --------- ------
voynich_real           520     489      8552     0.1710    0.940       50000         1    0.0
uniform              11316    3743      8548     0.1710    0.331       50000         1    0.0
voynich_freq         12116    4636      8420     0.1684    0.383       50000         1    0.0
markov_1             12145    4578      8492     0.1698    0.377       50000         1    0.0
shuffled             12106    4538      8525     0.1705    0.375       50000         1    0.0
bootstrap_only       11111    5555      6251     0.1250    0.500       50000         1    0.0
frobenius_only       22286       0     25132     0.5026    0.000       50000         1    0.0
random_walk          10165    2024      9046     0.1809    0.199       50000         1    0.0

=== KEY FINDINGS ===
  Zero entropy across ALL inputs: YES (engine invariant)
  Voynich-freq matches real paradox rate: YES
    Real paradox rate:  0.1710
    Freq-gen rate:      0.1684
  Bootstrap-only reaches steady state at step: 50000
  Bootstrap-only paradox rate: 0.1250
  Shuffled vs real active register diff: 11586
    (Large diff → sequential structure matters)

=== FOLIO MUTATION SCANNER ===

Compiling original corpus...
  Folios: 227
  Instructions: 44445
  Registers: 44423

Running baseline (unmutated)...
  Active: 345, Fixed: 264, Paradoxes: 2871, ParaRate: 0.1723

Phase 1 — Glyph importance (individual knockout):
  Glyph  Mnemonic   Operation                               ΔActive   ΔParadox
  ------ ---------- -------------------------------------- -------- ----------
  o      VINIT      Initial object ∅                            173        117
  p      TANCH      Terminal anchor ⊤                           173        117
  e      AFWD       Morphism →                                  173        117
  a      AREV       Contravariant inversion ←                   173        117
  d      CLINK      Composition ∘                               173        117
  s      ISCRIB     Identity id                                 173        117
  sh     FFUSE      Frobenius multiplication μ                  173        117
  t      EVALT      Lattice: True                               173        117
  k      EVALF      Lattice: False                              173        117
  r      ENGAGR     Lattice: Both (paradox)                     158      -1256
  ch     FSPLIT     Frobenius co-multiplication δ               155      -1496
  y      IFIX       Linear tape write                           147        117

  Load-bearing glyphs (|ΔActive| > 10): ['o', 'p', 'e', 'a', 'd', 's', 'ch', 'sh', 't', 'k', 'r', 'y']

Phase 2 — Mutation rate scan (substitution):
    Rate   Active  ΔActive   ParaRate  ΔParaRate   Instrs
  ------ -------- -------- ---------- ---------- --------
    0.01      518      173     0.1790     0.0067    44423
    0.05      515      170     0.1778     0.0055    44423
    0.10      521      176     0.1771     0.0049    44423
    0.20      520      175     0.1769     0.0046    44423
    0.30      519      174     0.1748     0.0025    44423
    0.50      515      170     0.1730     0.0008    44423

  ⚠ Structural degradation >10% at mutation rate: 0.01

Phase 3 — Section fragility (mutation rate=0.10):
  Section            Active  ΔActive   ParaRate  ΔParaRate
  ---------------- -------- -------- ---------- ----------
  balneological         518      173     0.1793     0.0071
  biological            518      173     0.1793     0.0071
  botanical             519      174     0.1788     0.0065
  cosmological          518      173     0.1783     0.0061

  Most fragile section: botanical (ΔActive=174)

=== SUMMARY ===
  Baseline active registers: 345
  Baseline paradox rate:     0.1723
  Critical glyphs:           o, p, e, a, d, s, ch, sh, t, k, r, y
  Engine robustness:         FRAGILE

=== PARADOX INJECTION ANALYZER ===

Compiling corpus...
  Folios:     227
  Registers:  44423
  Instructions: 44445

Phase 1 — Baseline run (50000 steps)...
  Active registers:      520
  Fixed registers:       489
  Paradox stabilizations: 8552
  Entropy Δ:             0.00000000 J/K

Phase 2 — Section paradox susceptibility...
  Section            Regs Injected   ΔParadox   Ampl/reg  ΔActive
  ---------------- ------ -------- ---------- ---------- --------
  balneological      8020      201        201       1.00      201
  biological         4125      207        207       1.00      207
  botanical         14810      201        201       1.00      201
  cosmological      17468      201        201       1.00      195

Phase 3 — Register susceptibility scan (stride=100)...

  Top 10 paradox amplifiers (highest Δ):
    r     0: +1 paradox stabilizations
    r   100: +1 paradox stabilizations
    r   200: +1 paradox stabilizations
    r   300: +1 paradox stabilizations
    r   400: +1 paradox stabilizations
    r   500: +1 paradox stabilizations
    r   600: +1 paradox stabilizations
    r   700: +1 paradox stabilizations
    r   800: +1 paradox stabilizations
    r   900: +1 paradox stabilizations

  Top 10 paradox sinks (lowest Δ):
    r     0: +1 paradox stabilizations
    r   100: +1 paradox stabilizations
    r   200: +1 paradox stabilizations
    r   300: +1 paradox stabilizations
    r   400: +1 paradox stabilizations
    r   500: +1 paradox stabilizations
    r   600: +1 paradox stabilizations
    r   700: +1 paradox stabilizations
    r   800: +1 paradox stabilizations
    r   900: +1 paradox stabilizations

=== SUMMARY ===
  Strongest amplifier: r0 (+1)
  Baseline paradox rate: 8552 / 50000 steps
  Paradox linearity:     CONFIRMED

=== REGISTER LIFECYCLE TRACKER ===

Compiling corpus...
  Folios: 227
  Registers: 44423
  Instructions: 44445

Sampling 2000 registers...

Phase 1 — Tracing register lifecycles (50000 steps)...
  Traced 21 registers.

Phase 2 — Lifespan distribution (fixed registers):
  Total fixed registers: 18
  Min lifespan: 0 steps
  Max lifespan: 22350 steps
  Mean lifespan: 7411.5 steps
  Median lifespan: 2972 steps

  Lifespan histogram (bucket size=2235):
         0-2235   :     7 ███████
      2235-4470   :     3 ███
      4470-6705   :     1 █
      6705-8940   :     1 █
     11175-13410  :     3 ███
     20115-22350  :     2 ██
     22350-24585  :     1 █

Phase 3 — Birth opcode → fixation latency:
  Birth Opcode    N Fixed  Mean Latency    Min    Max
  -------------- -------- ------------- ------ ------
  AFWD                  1        2090.0   2090   2090
  AREV                  1       21478.0  21478  21478
  CLINK                 4        7692.0   1595  13335
  ENGAGR                2       12206.0   2934  21478
  EVALT                 1       22350.0  22350  22350
  FFUSE                 1        8042.0   8042   8042
  FSPLIT                2        2934.5    232   5637
  IFIX                  1           0.0      0      0
  ISCRIB                1         559.0    559    559
  TANCH                 1         467.0    467    467
  VINIT                 3        5790.7   1506  12894

Phase 4 — Register survival curve:
    Step       0: 72.73% |█████████████████████████████░░░░░░░░░░░|
    Step    2500: 45.45% |██████████████████░░░░░░░░░░░░░░░░░░░░░░|
    Step    5000: 36.36% |██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step    7500: 27.27% |██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   10000: 27.27% |██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   12500: 26.67% |██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   15000: 20.00% |████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   17500: 30.00% |████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   20000: 30.00% |████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   22500: 25.00% |██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   25000: 20.00% |████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   27500: 20.00% |████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   30000: 20.00% |████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   32500: 23.81% |█████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   35000: 23.81% |█████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   37500: 23.81% |█████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   40000: 14.29% |█████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   42500: 14.29% |█████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   45000: 14.29% |█████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   47500: 14.29% |█████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
    Step   50000: 14.29% |█████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|

Phase 5 — Register families (birth gap ≤ 5 steps):
  Total families: 20
  Family size: min=1, max=2, mean=1.1
  Largest family: [503, 506]

  Family size distribution:
    Size    1:    19 ███████████████████
    Size    2:     1 █

Phase 6 — Paradox engagement statistics:
  Registers with paradox engagement: 17 / 21
  Registers with multiple engagements: 17
  Max engagements for single register: 36

=== SUMMARY ===
  Traced: 21, Fixed: 18, Paradox: 17
  Fixation rate: 85.71%

================================================================================
  VOYNICH ENGINE — MASTER ANALYSIS SUITE
================================================================================
  Data:    /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt
  Steps:   50000 (reduced: 16666 for heavy programs)
  Seed:    42
  Programs: 6
================================================================================

================================================================================
Running: Bootstrap Cycle Explorer
  Script: programs/bootstrap_explorer.py
  Desc:   Finds Frobenius cycles, spectral gap, transition matrix
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/bootstrap_explorer.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --max-mismatches 2
================================================================================


================================================================================
Running: Folio Topology Comparator
  Script: programs/folio_comparator.py
  Desc:   Per-folio structural fingerprints, JS divergence between sections
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/folio_comparator.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --top-n 10
================================================================================


================================================================================
Running: Synthetic EVA Comparator
  Script: programs/synthetic_comparator.py
  Desc:   Zero-entropy test, synthetic vs real engine behavior
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/synthetic_comparator.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --steps 50000 --seed 42
================================================================================


================================================================================
Running: Folio Mutation Scanner
  Script: programs/mutation_scanner.py
  Desc:   Glyph knockout, mutation rate scan, section fragility
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/mutation_scanner.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --steps 16666 --seed 42
================================================================================


================================================================================
Running: Paradox Injection Analyzer
  Script: programs/paradox_injector.py
  Desc:   Dialetheic stress testing, section paradox susceptibility
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/paradox_injector.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --steps 50000
================================================================================


================================================================================
Running: Register Lifecycle Tracker
  Script: programs/register_lifecycle.py
  Desc:   Individual register birth→fixation traces, survival curves
  Cmd:    /home/mrnob0dy666/voynich-engine/.venv/bin/python3 programs/register_lifecycle.py /home/mrnob0dy666/voynich-engine/data/LSI_ivtff_0d.txt --sample 2000 --steps 50000
================================================================================


================================================================================
  ANALYSIS SUMMARY
================================================================================
  Program                                    Status     Time
  ---------------------------------------- -------- --------
  Bootstrap Cycle Explorer                       OK     0.3s
  Folio Topology Comparator                      OK     0.3s
  Synthetic EVA Comparator                       OK     0.8s
  Folio Mutation Scanner                         OK     1.0s
  Paradox Injection Analyzer                     OK    15.3s
  Register Lifecycle Tracker                     OK     1.2s

  6/6 programs completed successfully.
================================================================================

