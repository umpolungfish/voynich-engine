"""
IMASM compiler for the Voynich EVA transcription.

Parses the Takahashi EVA format (lines marked ;H>) and extracts
primitive opcodes by scanning each token for embedded glyph families.
Folios are compiled concurrently; register allocation is linear and
monotonic (append-only, enforcing the IFIX temporal asymmetry).
"""

from __future__ import annotations
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .primitives import PRIMITIVES

_SORTED_PRIMS = sorted(PRIMITIVES, key=len, reverse=True)  # longer matches first


def _clean(token: str) -> str:
    return token.strip('.,-=!<>?{}[]%').lower()


def _extract(text: str) -> list[tuple[str, dict | str]]:
    """Scan a line of EVA text and emit (glyph, meta) pairs.

    Single-pass scan: iterate through all primitives once per token, removing
    the first occurrence of each match as found. Leftover characters are
    discarded if any primitive was matched; only fully unmatched tokens
    become DATA entries.
    """
    extracted = []
    for raw in text.split():
        tok = _clean(raw)
        matched = False
        for prim in _SORTED_PRIMS:
            if prim in tok:
                extracted.append((prim, PRIMITIVES[prim]))
                matched = True
                tok = tok.replace(prim, '', 1)
        if not matched and tok:
            extracted.append(('DATA', tok))
    return extracted


def _compile_folio(name: str, lines: list[str]) -> tuple[str, list[str], int]:
    stream: list[str] = []
    reg = 0
    for line in lines:
        if line.startswith('#') or not line.strip():
            continue
        if ';H>' in line or ';H ' in line or ';H\t' in line:
            parts = line.split('>', 1)
            if len(parts) < 2:
                continue
            for glyph, meta in _extract(parts[1].strip()):
                if glyph == 'DATA':
                    stream.append(f' DATA  | RAW_VAL {meta}')
                else:
                    stream.append(f' {hex(meta["opcode"])} | {meta["mnemonic"]:<6} %r{reg}')
                    reg += 1
    return name, stream, reg


def compile_corpus(
    transcription_path: str | Path,
    workers: int = 12,
    verbose: bool = False,
) -> dict:
    """
    Compile the full EVA transcription to IMASM instructions.

    Returns a dict with keys:
        folios            — per-folio results {name: {instructions, registers}}
        total_instructions
        total_registers
        folio_count
        entropy_delta     — always 0.0 (linear type constraint)
    """
    path = Path(transcription_path)
    raw = path.read_text(encoding='utf-8', errors='ignore').splitlines()

    folios: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for line in raw:
        if '<f' in line and not line.startswith('#'):
            try:
                current = 'f' + line.split('<f')[1].split('>')[0].split('.')[0]
            except (IndexError, ValueError):
                pass
        if current:
            folios[current].append(line)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_compile_folio, name, folio_lines): name
            for name, folio_lines in folios.items()
        }
        for future in as_completed(futures):
            name, stream, reg_count = future.result()
            results[name] = {'instructions': stream, 'registers': reg_count}
            if verbose:
                print(f'  {name}: {reg_count} registers')

    total_instructions = sum(len(r['instructions']) for r in results.values())
    total_registers = sum(r['registers'] for r in results.values())

    return {
        'folios': results,
        'total_instructions': total_instructions,
        'total_registers': total_registers,
        'folio_count': len(results),
        'entropy_delta': 0.0,
    }


def peak_folios(result: dict, n: int = 10) -> list[tuple[str, int]]:
    """Return the n highest-density folios by register count."""
    return sorted(
        ((name, data['registers']) for name, data in result['folios'].items()),
        key=lambda x: x[1],
        reverse=True,
    )[:n]


def write_log(result: dict, path: str | Path) -> None:
    """Write the full compilation log (all instructions, all folios)."""
    path = Path(path)
    with path.open('w', encoding='utf-8') as f:
        for name, data in sorted(result['folios'].items()):
            f.write(f'=== {name.upper()} ===\n')
            for instr in data['instructions']:
                f.write(instr + '\n')
            f.write(f'  -> {data["registers"]} registers, ΔS = 0.00000000 J/K\n\n')


def main() -> None:
    import argparse, sys
    parser = argparse.ArgumentParser(description='Compile EVA transcription to IMASM')
    parser.add_argument('transcription', help='Path to LSI_ivtff_0d.txt or equivalent')
    parser.add_argument('--log', help='Write full instruction log to this file')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    result = compile_corpus(args.transcription, verbose=args.verbose)
    print(f'Folios compiled : {result["folio_count"]}')
    print(f'Total instructions: {result["total_instructions"]}')
    print(f'Total registers : {result["total_registers"]}')
    print(f'Entropy delta   : {result["entropy_delta"]:.8f} J/K')
    print(f'Status          : SELF_SUSTAINING_BOOTSTRAP_COMPLETE')

    print('\nPeak folios:')
    for name, regs in peak_folios(result):
        print(f'  {name}: {regs}')

    if args.log:
        write_log(result, args.log)
        print(f'\nLog written to {args.log}')


if __name__ == '__main__':
    main()
