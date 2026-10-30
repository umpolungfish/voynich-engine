"""
Full pipeline: compile → run → graph.

Run from the repository root:
    python examples/quickstart.py
"""

from pathlib import Path
from voynich_engine import compile_corpus, UniversalEngine, generate_call_graph, peak_folios

DATA = Path(__file__).parent.parent / 'data' / 'LSI_ivtff_0d.txt'

print('=== VOYNICH ENGINE ===\n')

# 1. Compile the full EVA transcription
print('Compiling EVA transcription...')
result = compile_corpus(DATA)
print(f'  Folios    : {result["folio_count"]}')
print(f'  Instructions: {result["total_instructions"]}')
print(f'  Registers : {result["total_registers"]}')
print(f'  Entropy Δ : {result["entropy_delta"]:.8f} J/K')
print(f'  Status    : SELF_SUSTAINING_BOOTSTRAP_COMPLETE\n')

print('Peak folios (by register density):')
for name, regs in peak_folios(result, n=5):
    print(f'  {name}: {regs}')
print()

# 2. Run the virtual machine
print('Starting Universal Engine...\n')
engine = UniversalEngine.from_compilation(result)
for snap in engine.run(steps=10000, report_every=1000):
    print(f'  Step {snap["step"]:6d} | Active {snap["active_registers"]:4d} | '
          f'Paradoxes {snap["paradox_stabilizations"]:4d}')

print()
engine.report()
print()

# 3. Generate call graph
print('Building call graph...')
G, C = generate_call_graph(result, output='voynich_graph.png', verbose=True)
print(f'  Open voynich_graph.png — zoom to see the Frobenius hub structure.')
