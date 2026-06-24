"""
Voynich session runner — CLI for the six-gate session protocol.

  python programs/session_runner.py --folio f11r --para 6
  python programs/session_runner.py --potency summa
  python programs/session_runner.py --part root --apply oral
  python programs/session_runner.py --list-summa

By default, data is read from ../voynich_integrated/ relative to this file
and the transcription from data/LSI_ivtff_0d.txt relative to the package root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running as a script without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from voynich_engine.session import VoynichSession

_HERE = Path(__file__).parent.parent                       # voynich-engine root
_DEFAULT_DATA  = _HERE.parent.parent / 'ig-docs' / 'voynich_integrated'
_DEFAULT_TRANS = _HERE / 'data' / 'LSI_ivtff_0d.txt'


def _list_summa(sess: VoynichSession) -> None:
    hits = sess.find_entries(potency='summa')
    print(f'Summa potency entries ({len(hits)}):')
    for e in hits:
        print(f'  {e.folio}/p{e.para}  n_ops={e.n_ops:2d}  '
              f'{e.pars_plantae:<32}  {e.forma}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Voynich six-gate session runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--folio',   metavar='F',    help='Pharmaceutical folio (e.g. f11r)')
    parser.add_argument('--para',    metavar='N', type=int, help='Paragraph within folio')
    parser.add_argument('--potency', metavar='P',    help='Potency filter (summa/alta/media/debilis)')
    parser.add_argument('--part',    metavar='PART', help='Plant part filter (root/leaf/flower)')
    parser.add_argument('--apply',   metavar='APP',  help='Application filter (oral/inhalation/cutaneous)')
    parser.add_argument('--forma',   metavar='FORM', help='Pharmaceutical form filter (pulvis/tinctura/…)')
    parser.add_argument('--list-summa', action='store_true', help='List all summa potency entries and exit')
    parser.add_argument('--data-dir',   metavar='DIR', default=str(_DEFAULT_DATA),
                        help=f'Path to voynich_integrated/ directory (default: {_DEFAULT_DATA})')
    parser.add_argument('--transcription', metavar='FILE', default=str(_DEFAULT_TRANS),
                        help='Path to LSI_ivtff_0d.txt for Gate 2 compilation')
    args = parser.parse_args()

    trans = Path(args.transcription)
    sess = VoynichSession(
        data_dir=args.data_dir,
        transcription=trans if trans.exists() else None,
    )

    if args.list_summa:
        _list_summa(sess)
        return

    if not any([args.folio, args.para, args.potency, args.part, args.apply, args.forma]):
        parser.print_help()
        sys.exit(0)

    state = sess.run(
        folio=args.folio,
        para=args.para,
        potency=args.potency,
        pars_plantae=args.part,
        applicatio=args.apply,
        forma=args.forma,
    )
    sess.report(state)

    # exit code reflects session outcome
    sys.exit(0 if state.gate3_passed else 1)


if __name__ == '__main__':
    main()
