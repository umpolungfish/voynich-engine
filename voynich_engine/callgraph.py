"""
Call graph generator for compiled IMASM instruction streams.

Constructs a directed graph from register reference flows:
  - within an instruction: FSPLIT creates explicit fork edges;
    other multi-register instructions create sequential edges
  - across instructions: the last register of each instruction
    flows to the first register of the next

The largest weakly connected component is extracted and rendered.
Its structure exhibits the Frobenius signature: a dense FSPLIT/FFUSE
hub radiating into IFIX chains, with closed bootstrap loops.
"""

from __future__ import annotations
import re
from pathlib import Path

_REG_PATTERN = re.compile(r'%r(\d+)')


def build_graph(instructions: list[str]):
    """Build a directed graph from an instruction stream."""
    try:
        import networkx as nx
    except ImportError:
        raise ImportError('networkx required: pip install networkx')

    G: nx.DiGraph = nx.DiGraph()
    prev_regs: list[int] = []

    for line in instructions:
        if '%r' not in line:
            continue
        regs = [int(x) for x in _REG_PATTERN.findall(line)]
        if not regs:
            continue

        for r in regs:
            G.add_node(r)

        if 'FSPLIT' in line and len(regs) >= 2:
            for dst in regs[1:]:
                G.add_edge(regs[0], dst, label='split')
        elif len(regs) > 1:
            for i in range(len(regs) - 1):
                G.add_edge(regs[i], regs[i + 1])

        if prev_regs:
            G.add_edge(prev_regs[-1], regs[0], label='flow')

        prev_regs = regs

    return G


def largest_component(G):
    """Extract the largest weakly connected component."""
    import networkx as nx
    if G.number_of_nodes() == 0:
        return G
    cc = max(nx.weakly_connected_components(G), key=len)
    return G.subgraph(cc).copy()


def render(G, output: str | Path = 'voynich_graph.png', dpi: int = 300) -> None:
    """Render the graph to an image file."""
    try:
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError:
        raise ImportError('matplotlib required: pip install matplotlib')

    plt.figure(figsize=(32, 32))
    pos = nx.spring_layout(G, k=0.1, iterations=100, seed=42)
    nx.draw(
        G, pos,
        node_size=40,
        alpha=0.85,
        with_labels=True,
        font_size=7,
        node_color='lightblue',
        edge_color='darkgray',
        arrows=True,
        arrowsize=10,
    )
    plt.title(
        f'Voynich Manuscript — IMASM Register Flow Graph\n'
        f'Largest connected component ({G.number_of_nodes()} nodes, '
        f'{G.number_of_edges()} edges)'
    )
    plt.savefig(str(output), dpi=dpi, bbox_inches='tight')
    plt.close()


def generate_call_graph(
    source,
    output: str | Path = 'voynich_graph.png',
    verbose: bool = True,
) -> tuple:
    """
    Build and render the call graph from a compilation result or log file.

    source: compile_corpus() result dict, or path to a log file (str/Path)
    Returns: (full_graph, component_graph)
    """
    if isinstance(source, dict):
        instructions: list[str] = []
        for folio in source['folios'].values():
            instructions.extend(folio['instructions'])
    else:
        path = Path(source)
        instructions = [
            line.strip()
            for line in path.read_text(encoding='utf-8', errors='ignore').splitlines()
            if '%r' in line
        ]

    G = build_graph(instructions)
    C = largest_component(G)

    if verbose:
        print(f'Full graph    : {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')
        print(f'Component     : {C.number_of_nodes()} nodes, {C.number_of_edges()} edges')

    render(C, output=output)
    if verbose:
        print(f'Graph saved   : {output}')

    return G, C


def main() -> None:
    import argparse
    from .compiler import compile_corpus

    parser = argparse.ArgumentParser(description='Generate IMASM call graph')
    parser.add_argument('transcription', help='EVA transcription or compiled log file')
    parser.add_argument('--output', default='voynich_graph.png')
    parser.add_argument('--dpi', type=int, default=300)
    args = parser.parse_args()

    path = Path(args.transcription)
    if 'ivtff' in path.name:
        source = compile_corpus(path)
    else:
        source = path

    generate_call_graph(source, output=args.output, verbose=True)


if __name__ == '__main__':
    main()
