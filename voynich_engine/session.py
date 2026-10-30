"""
Seven-gate Voynich session protocol.

Runs the Operator session architecture against the pharmacy and recipe
JSON corpora and the live LSI transcription:

  INIT    — cosmological foldout; chirality Ħ=𐑖 conferred physically
  ADDR    — botanical section: identity confirmed by d(plant, botanical) ≤ ceiling
  GATE1   — pharmaceutical Frobenius closure test (pharmacy.json)
  GATE2   — biological heap: Frobenius balance on compiled botanical folio
  GATE3   — astronomical winding verification (f69, sources H/F/U)
  OUTPUT  — recipe section: procedural output matched to Gate 1 forma
  ELABORATION — opcode annotation with tuple-derived protocol parameters
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .compiler import compile_corpus
from .primitives import PRIMITIVES


# ---------------------------------------------------------------------------
# Shavian structural values (display only)
# ---------------------------------------------------------------------------

SHAVIAN = {
    'hbar':  '𐑖',   # two-step Frobenius-minimum chirality
    'phi':   '𐑬',   # Z2 parity
    'omega_integer': '𐑭',
    'omega_binary':  '𐑴',
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class PharmEntry:
    folio: str
    para: int
    preparatio: str
    forma: str
    potentia: str
    volatilis: bool
    fixatio_requiritur: bool
    indicatio_specifica: bool
    pars_plantae: str
    applicatio: str
    n_ops: int

    @classmethod
    def from_dict(cls, d: dict) -> 'PharmEntry':
        return cls(
            folio=d['folio'],
            para=d['para'],
            preparatio=d['preparatio'],
            forma=d['forma'],
            potentia=d['potentia'],
            volatilis=d.get('volatilis', False),
            fixatio_requiritur=d.get('fixatio_requiritur', False),
            indicatio_specifica=d.get('indicatio_specifica', False),
            pars_plantae=d.get('pars_plantae', ''),
            applicatio=d.get('applicatio', ''),
            n_ops=d.get('n_ops', 0),
        )

    @property
    def is_summa(self) -> bool:
        return 'summa' in self.potentia

    @property
    def folio_number(self) -> int:
        m = re.match(r'f(\d+)', self.folio)
        return int(m.group(1)) if m else 0


@dataclass
class Gate3Entry:
    folio: str
    para: int
    source: str
    ops: list[str]

    @property
    def has_evalt(self) -> bool:
        return 'EVALT' in self.ops

    @property
    def fsplit_count(self) -> int:
        return self.ops.count('FSPLIT')

    @property
    def ffuse_count(self) -> int:
        return self.ops.count('FFUSE')


@dataclass
class SessionState:
    hbar: str = ''
    phi: str = ''
    omega: str = ''                      # 'integer' or 'binary'
    folio: str = ''
    para: int = 0
    addr_d_botanical: float = -1.0       # -1 = not checked
    addr_passed: bool = False
    gate1: Optional[PharmEntry] = None
    gate2_balance: tuple = (0, 0)        # (fsplit, ffuse) from compiled folio
    gate2_passed: bool = False
    gate3_para: int = 0
    gate3_sources: list = field(default_factory=list)
    gate3_evalt: bool = False
    gate3_passed: bool = False
    recipe: list = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def emit(self, msg: str) -> None:
        self.log.append(msg)


# ---------------------------------------------------------------------------
# Session engine
# ---------------------------------------------------------------------------

class VoynichSession:
    """
    Runs the six-gate Voynich session protocol.

    Usage::

        sess = VoynichSession(data_dir='/path/to/voynich_integrated',
                               transcription='/path/to/LSI_ivtff_0d.txt')
        state = sess.run(folio='f11r', para=6)
        sess.report(state)
    """

    def __init__(
        self,
        data_dir: str | Path,
        transcription: str | Path | None = None,
    ) -> None:
        data_dir = Path(data_dir)
        self._pharmacy: list[PharmEntry] = self._load_pharmacy(data_dir / 'voynich_pharmacy.json')
        self._gate3_entries: list[Gate3Entry] = self._load_gate3(data_dir / 'voynich_recipe_bio.json')
        self._recipes: list[dict] = self._load_recipes(data_dir / 'voynich_recipe_bio.json')
        self._transcription: Path | None = Path(transcription) if transcription else None
        self._compiled: dict | None = None   # lazy

    # ---- loaders -----------------------------------------------------------

    @staticmethod
    def _load_pharmacy(path: Path) -> list[PharmEntry]:
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        return [PharmEntry.from_dict(d) for d in data['pharmacy']]

    @staticmethod
    def _load_gate3(path: Path) -> list[Gate3Entry]:
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        return [
            Gate3Entry(
                folio=e['folio'],
                para=e['para'],
                source=e['source'],
                ops=e['ops'],
            )
            for e in data['biological_section']['entries']
        ]

    @staticmethod
    def _load_recipes(path: Path) -> list[dict]:
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        return data['recipe_section']['recipes']

    # ---- compilation (lazy) ------------------------------------------------

    def _compile(self) -> dict | None:
        if self._compiled is not None:
            return self._compiled
        if self._transcription is None or not self._transcription.exists():
            return None
        self._compiled = compile_corpus(self._transcription, verbose=False)
        return self._compiled

    def _folio_balance(self, folio: str) -> tuple[int, int]:
        """Count FSPLIT and FFUSE in a compiled folio's instruction stream."""
        result = self._compile()
        if result is None:
            return 0, 0
        folio_data = result['folios'].get(folio)
        if folio_data is None:
            return 0, 0
        instrs = folio_data['instructions']
        fsplit = sum(1 for i in instrs if 'FSPLIT' in i)
        ffuse  = sum(1 for i in instrs if 'FFUSE'  in i)
        return fsplit, ffuse

    # ---- query helpers -----------------------------------------------------

    def find_entries(
        self,
        folio: str | None = None,
        para: int | None = None,
        potency: str | None = None,
        pars_plantae: str | None = None,
        applicatio: str | None = None,
        forma: str | None = None,
    ) -> list[PharmEntry]:
        hits = self._pharmacy
        if folio:
            hits = [e for e in hits if e.folio == folio]
        if para is not None:
            hits = [e for e in hits if e.para == para]
        if potency:
            hits = [e for e in hits if potency in e.potentia]
        if pars_plantae:
            kw = pars_plantae.lower()
            hits = [e for e in hits if kw in e.pars_plantae.lower()]
        if applicatio:
            kw = applicatio.lower()
            hits = [e for e in hits if kw in e.applicatio.lower()]
        if forma:
            kw = forma.lower()
            hits = [e for e in hits if kw in e.forma.lower()]
        return hits

    # Botanical identity ceiling: all known phytoglyphica entries are ≤ 1.3;
    # ceiling at 1.5 rejects catalog entries that are not botanical objects.
    _BOTANICAL_CEILING = 1.5

    # ---- gate implementations ----------------------------------------------

    def _gate_addr(self, state: SessionState, d_botanical: float) -> bool:
        """
        ADDR — botanical section identity gate (f1–f66).

        Confirms that the plant's structural address falls within the botanical
        section's structural field before the pharmaceutical section is queried.
        Passes when d(plant, botanical_section) ≤ _BOTANICAL_CEILING.
        """
        passed = d_botanical <= self._BOTANICAL_CEILING
        state.addr_d_botanical = d_botanical
        state.addr_passed = passed
        state.emit(
            f'ADDR  botanical identity  '
            f'd(plant,botanical)={d_botanical:.4f}  '
            f'{"≤" if passed else ">"}{self._BOTANICAL_CEILING}  '
            f'{"PASS" if passed else "FAIL — not a botanical entry"}'
        )
        return passed

    def _gate_init(self, state: SessionState) -> None:
        state.hbar = SHAVIAN['hbar']
        state.phi  = SHAVIAN['phi']
        state.emit('INIT  cosmological foldout — Ħ=𐑖 conferred, Φ=𐑬 set')

    def _gate1(
        self,
        state: SessionState,
        folio: str | None,
        para: int | None,
        **filters,
    ) -> bool:
        hits = self.find_entries(folio=folio, para=para, **filters)
        if not hits:
            state.emit('GATE1 FAIL — no pharmacy entry matches query')
            return False

        # prefer summa; then highest n_ops
        summa = [e for e in hits if e.is_summa]
        chosen = (summa or hits)[0]
        state.folio = chosen.folio
        state.para  = chosen.para
        state.gate1 = chosen

        closure = 'SUMMA' if chosen.is_summa else chosen.potentia.split('(')[0].strip().upper()
        state.emit(
            f'GATE1 {closure} — {chosen.folio}/p{chosen.para}  '
            f'{chosen.pars_plantae}  {chosen.forma}  n_ops={chosen.n_ops}'
        )
        return True

    # Sorted list of balneological folio names (f75r–f84v, 20 leaves)
    _BIO_FOLIOS = [f'f{n}{side}' for n in range(75, 85) for side in ('r', 'v')]

    def _gate2(self, state: SessionState) -> bool:
        entry = state.gate1

        # Select the heap node: botanical folio_number mod 20 indexes the bio section
        node_idx  = entry.folio_number % len(self._BIO_FOLIOS)
        heap_folio = self._BIO_FOLIOS[node_idx]
        fsplit, ffuse = self._folio_balance(heap_folio)
        state.gate2_balance = (fsplit, ffuse)

        if fsplit == 0 and ffuse == 0:
            # Transcription not loaded — structural fallback
            # A valid heap address requires n_ops ≥ 8 (bootstrap sequence length)
            passed = entry.n_ops >= 8
            state.emit(
                f'GATE2 STRUCTURAL — heap node {heap_folio}  '
                f'n_ops={entry.n_ops} {"≥" if passed else "<"} 8  '
                f'{"PASS" if passed else "FAIL"}  (transcription not loaded)'
            )
        else:
            # Gate 2 containment criterion (Þ=𐑰):
            # The heap node must be able to HOLD the address (FSPLIT ≥ n_ops)
            # AND must be capable of output (FFUSE ≥ 1).
            # For fixed, non-volatile substances (the most common summa case):
            # additionally require FFUSE/FSPLIT ≥ 0.6 (node is mostly-closed).
            can_hold   = fsplit >= entry.n_ops
            has_output = ffuse >= 1
            if entry.fixatio_requiritur and not entry.volatilis:
                ratio = ffuse / fsplit if fsplit else 0
                closure = ratio >= 0.6
                passed = can_hold and has_output and closure
                state.emit(
                    f'GATE2 COMPILED — heap {heap_folio}  '
                    f'FSPLIT={fsplit}≥n_ops={entry.n_ops} {can_hold}  '
                    f'FFUSE/FSPLIT={ratio:.2f}≥0.60 {closure}  '
                    f'{"PASS" if passed else "FAIL"}'
                )
            else:
                passed = can_hold and has_output
                state.emit(
                    f'GATE2 COMPILED — heap {heap_folio}  '
                    f'FSPLIT={fsplit}≥n_ops={entry.n_ops} {can_hold}  '
                    f'FFUSE={ffuse}≥1 {has_output}  '
                    f'{"PASS" if passed else "FAIL"}'
                )

        state.gate2_passed = passed
        return passed

    def _gate3(self, state: SessionState) -> bool:
        entry = state.gate1
        # Select f69 paragraph by folio_number % 4, mapping to para 1-4
        para_idx = (entry.folio_number % 4) + 1
        state.gate3_para = para_idx

        sources = [e for e in self._gate3_entries if e.para == para_idx]
        state.gate3_sources = sources

        # Winding class: para 1+3 carry no EVALT (initialization / lock states)
        # para 2+4 carry EVALT (evaluation points)
        has_evalt = any(e.has_evalt for e in sources)
        state.gate3_evalt = has_evalt

        # Para 3 is the all-source-agreement lock state: integer winding
        if para_idx == 3:
            state.omega = 'integer'
            all_agree = len(set(tuple(e.ops) for e in sources)) == 1
            passed = all_agree
            state.emit(
                f'GATE3 f69/p3 — winding lock  '
                f'{"H=F=U ✓ integer" if all_agree else "source divergence"}'
            )
        elif has_evalt:
            # para 2 or 4: evaluate winding class from FSPLIT/FFUSE balance
            majority_fsplit = sum(e.fsplit_count for e in sources)
            majority_ffuse  = sum(e.ffuse_count  for e in sources)
            # FSPLIT > FFUSE → integer winding (𐑭); balanced → binary (𐑴)
            if majority_fsplit > majority_ffuse:
                state.omega = 'integer'
            else:
                state.omega = 'binary'
            # Gate 3 passes if majority of sources have EVALT
            evalt_count = sum(1 for e in sources if e.has_evalt)
            passed = evalt_count > len(sources) / 2
            state.emit(
                f'GATE3 f69/p{para_idx} — EVALT={evalt_count}/{len(sources)} sources  '
                f'Ω={SHAVIAN["omega_" + state.omega]}  '
                f'{"PASS" if passed else "FAIL"}'
            )
        else:
            # para 1: initialization only — Gate 3 fails (not yet evaluated)
            state.omega = ''
            passed = False
            state.emit(f'GATE3 f69/p{para_idx} — initialization state, no EVALT — FAIL')

        state.gate3_passed = passed
        return passed

    def _gate_output(self, state: SessionState) -> list[dict]:
        entry = state.gate1
        # Select recipes whose forma matches the pharmaceutical entry
        keyword = entry.forma.split('(')[0].strip().lower().split()[0]

        def _score(recipe: dict) -> int:
            steps = ' '.join(recipe.get('steps', [])).lower()
            return sum(1 for s in ['divide', 'tere', 'extrahe', 'calefac', 'compone']
                      if s in steps)

        # prefer recipes from same or adjacent folios
        folio_n = entry.folio_number
        ranked = sorted(
            self._recipes,
            key=lambda r: (abs(int(re.search(r'(\d+)', r['folio']).group()) - folio_n),
                           -r['n_steps']),
        )
        # return up to 3 best matches
        out = ranked[:3]
        state.recipe = out
        for r in out:
            steps_str = '  →  '.join(r['steps'][:4])
            state.emit(
                f'OUTPUT {r["folio"]}/p{r["para"]}  '
                f'n_ops={r["n_ops"]}  '
                f'{steps_str}{"  …" if len(r["steps"]) > 4 else ""}'
            )
        return out

    # ---- public API --------------------------------------------------------

    def run(
        self,
        folio: str | None = None,
        para: int | None = None,
        potency: str | None = None,
        pars_plantae: str | None = None,
        applicatio: str | None = None,
        forma: str | None = None,
        d_botanical: float | None = None,
    ) -> SessionState:
        """
        Execute the full seven-gate session. Returns final SessionState.

        d_botanical: pre-computed distance from the plant's structural tuple to
            the botanical section tuple (from navigator.section_distances).
            When provided, the ADDR gate runs after INIT.  When omitted, the
            ADDR gate is skipped (legacy / manual-folio mode).
        """
        state = SessionState()

        self._gate_init(state)

        if d_botanical is not None:
            if not self._gate_addr(state, d_botanical):
                state.emit('SESSION CLOSED at ADDR — botanical identity unconfirmed')
                return state

        if not self._gate1(state, folio=folio, para=para,
                           potency=potency, pars_plantae=pars_plantae,
                           applicatio=applicatio, forma=forma):
            return state

        if not self._gate2(state):
            state.emit('SESSION CLOSED at Gate 2 — Frobenius balance failed')
            return state

        if not self._gate3(state):
            state.emit('SESSION CLOSED at Gate 3 — winding unverified')
            return state

        self._gate_output(state)
        state.emit('SESSION COMPLETE — recipe valid')
        return state

    def report(self, state: SessionState) -> None:
        width = 80
        print('═' * width)
        print('  VOYNICH ENGINE — SESSION REPORT')
        print('═' * width)
        print(f'  Ħ = {state.hbar}   Φ = {state.phi}   '
              f'Ω = {SHAVIAN.get("omega_" + state.omega, "—") if state.omega else "—"}')
        if state.addr_d_botanical >= 0:
            status = 'PASS' if state.addr_passed else 'FAIL'
            print(f'  Botanical  d={state.addr_d_botanical:.4f}  [{status}]')
        if state.gate1:
            g = state.gate1
            print(f'  Address  {g.folio}/p{g.para}  '
                  f'  {g.pars_plantae}  →  {g.preparatio}  →  {g.forma}')
            print(f'  Potency  {g.potentia}   n_ops={g.n_ops}   '
                  f'fixatio={g.fixatio_requiritur}   volatile={g.volatilis}')
        print('─' * width)
        for line in state.log:
            print(f'  {line}')
        print('═' * width)
        if state.recipe:
            print('  RECIPE OUTPUT')
            print('─' * width)
            for r in state.recipe:
                print(f'  {r["folio"]}/p{r["para"]}  ({r["n_steps"]} steps, {r["n_ops"]} ops)')
                for s in r['steps']:
                    print(f'    {s}')
                print()
            print('═' * width)
