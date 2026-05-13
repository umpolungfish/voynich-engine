"""
The twelve EVA glyph families as categorical opcodes.

Each entry maps an EVA glyph (or digraph) to its categorical operation
in the Universal Imscriptive Grammar. The correspondence is structural,
not assigned: the glyph families of the Voynich EVA transcription are
the categorical primitives at token resolution.
"""

PRIMITIVES: dict[str, dict] = {
    'o':  {'opcode': 0x0, 'mnemonic': 'VINIT',  'operation': 'Initial object ∅',            'family': 'logical'},
    'p':  {'opcode': 0x1, 'mnemonic': 'TANCH',  'operation': 'Terminal anchor ⊤',           'family': 'logical'},
    'e':  {'opcode': 0x2, 'mnemonic': 'AFWD',   'operation': 'Morphism →',                  'family': 'logical'},
    'a':  {'opcode': 0x3, 'mnemonic': 'AREV',   'operation': 'Contravariant inversion ←',   'family': 'logical'},
    'd':  {'opcode': 0x4, 'mnemonic': 'CLINK',  'operation': 'Composition ∘',               'family': 'logical'},
    's':  {'opcode': 0x5, 'mnemonic': 'ISCRIB', 'operation': 'Identity id',                 'family': 'logical'},
    'ch': {'opcode': 0x6, 'mnemonic': 'FSPLIT', 'operation': 'Frobenius co-multiplication δ', 'family': 'frobenius'},
    'sh': {'opcode': 0x7, 'mnemonic': 'FFUSE',  'operation': 'Frobenius multiplication μ',  'family': 'frobenius'},
    't':  {'opcode': 0x8, 'mnemonic': 'EVALT',  'operation': 'Lattice: True',               'family': 'dialetheia'},
    'k':  {'opcode': 0x9, 'mnemonic': 'EVALF',  'operation': 'Lattice: False',              'family': 'dialetheia'},
    'r':  {'opcode': 0xA, 'mnemonic': 'ENGAGR', 'operation': 'Lattice: Both (paradox)',     'family': 'dialetheia'},
    'y':  {'opcode': 0xB, 'mnemonic': 'IFIX',   'operation': 'Linear tape write',           'family': 'linear'},
}

# Four-valued flux lattice for Tri-Phase registers
FLUX = {
    '00': 'Void',
    '01': 'True',
    '10': 'False',
    '11': 'Both',
}

# The bootstrap core: identity ∘ reverse ∘ split ∘ forward ∘ fuse ∘ link ∘ fix ∘ identity
BOOTSTRAP_SEQUENCE = ['s', 'a', 'ch', 'e', 'sh', 'd', 'y', 's']
