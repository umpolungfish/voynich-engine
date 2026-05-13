"""
Sectional call-graph generator.

Produces per-folio register-flow graphs colour-coded by manuscript section
(botanical, biological, balneological, cosmological). Optionally animates
the full engine execution as a folio-by-folio progression (requires ffmpeg).
"""

from __future__ import annotations
import re
from pathlib import Path

import networkx as nx

from .callgraph import build_graph, largest_component

_REG_PATTERN = re.compile(r'%r(\d+)')

_SECTIONS = [
    (range(1,   67),  'botanical',     'green'),
    (range(67,  75),  'biological',    'orange'),
    (range(75,  85),  'balneological', 'purple'),
    (range(85, 117),  'cosmological',  'blue'),
]


def classify_folio(folio: str) -> tuple[str, str]:
    """Return (section_name, colour) for a folio identifier."""
    m = re.match(r'f?(\d+)', folio.lower())
    if not m:
        return 'other', 'gray'
    n = int(m.group(1))
    for rng, name, color in _SECTIONS:
        if n in rng:
            return name, color
    return 'other', 'gray'


def _folio_instructions(source) -> dict[str, list[str]]:
    """Extract per-folio instruction lists from a result dict or log file."""
    if isinstance(source, dict):
        return {name: data['instructions'] for name, data in source['folios'].items()}

    path = Path(source)
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        stripped = line.strip()
        if stripped.startswith('=== ') and stripped.endswith(' ==='):
            current = stripped[4:-4].lower()
            result[current] = []
        elif current is not None and '%r' in line:
            result[current].append(stripped)
    return result


def _render_folio(G, color: str, section: str, folio: str, output_dir: Path, dpi: int) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(24, 24))
    pos = nx.spring_layout(G, k=0.15, iterations=80, seed=42)
    nx.draw(G, pos,
            node_size=60, alpha=0.9, with_labels=True, font_size=8,
            node_color=color, edge_color='darkgray', arrows=True, arrowsize=12)
    plt.title(
        f"Voynich {folio} — {section.upper()} section\n"
        f"({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)",
        fontsize=16,
    )
    out = output_dir / f"{folio}_{section}.png"
    plt.savefig(str(out), dpi=dpi, bbox_inches='tight')
    plt.close()


def _animate(folio_nodes: dict[str, set[int]], G_full, output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    print("Rendering animation (requires ffmpeg) ...")
    folio_list = sorted(folio_nodes.keys())
    all_nodes = list(G_full.nodes())
    pos = nx.spring_layout(G_full, k=0.1, iterations=100, seed=42)

    fig, ax = plt.subplots(figsize=(28, 28))

    def update(frame):
        ax.clear()
        current = folio_list[frame % len(folio_list)]
        highlight = folio_nodes[current]
        section, color = classify_folio(current)
        node_colors = [color if n in highlight else 'lightgray' for n in all_nodes]
        nx.draw(G_full, pos, ax=ax,
                node_size=40, alpha=0.85, with_labels=True, font_size=6,
                node_color=node_colors, edge_color='gray', arrows=True)
        ax.set_title(f"Engine — {current} [{section}] (frame {frame})", fontsize=14)
        return (ax,)

    ani = FuncAnimation(fig, update, frames=min(200, len(folio_list)), interval=300, repeat=True)
    out = str(output_dir / 'voynich_full_execution_animation.mp4')
    ani.save(out, writer='ffmpeg', fps=4, dpi=200)
    plt.close()
    print(f"Animation saved: {out}")


def generate_sectional_graphs(
    source,
    output_dir: str | Path = 'voynich_graphs',
    animate: bool = False,
    min_nodes: int = 5,
    dpi: int = 300,
) -> dict[str, tuple]:
    """
    Generate per-folio register-flow graphs, colour-coded by section.

    source:     compile_corpus() result dict, or path to a log file (str/Path)
    output_dir: directory for PNG files (and animation MP4 if animate=True)
    animate:    render a folio-progression MP4 (requires ffmpeg)
    min_nodes:  skip folios whose component has fewer nodes than this
    Returns:    {folio_name: (full_graph, component_graph)}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating sectional graphs → {output_dir}/")

    by_folio = _folio_instructions(source)
    results: dict[str, tuple] = {}
    folio_nodes: dict[str, set[int]] = {}
    G_full = nx.DiGraph()

    for folio, instructions in sorted(by_folio.items()):
        G = build_graph(instructions)
        G_full = nx.compose(G_full, G)

        nodes = {int(r) for line in instructions for r in _REG_PATTERN.findall(line)}
        if nodes:
            folio_nodes[folio] = nodes

        C = largest_component(G)
        if C.number_of_nodes() < min_nodes:
            continue

        section, color = classify_folio(folio)
        _render_folio(C, color, section, folio, output_dir, dpi)
        results[folio] = (G, C)
        print(f"  {folio} [{section}] — {C.number_of_nodes()} nodes, {C.number_of_edges()} edges")

    print(f"\nFull composite graph: {G_full.number_of_nodes()} nodes, {G_full.number_of_edges()} edges")

    if animate:
        _animate(folio_nodes, G_full, output_dir)

    print(f"\n=== {len(results)} sectional graphs written to {output_dir}/ ===")
    return results


def main() -> None:
    import argparse
    from .compiler import compile_corpus

    parser = argparse.ArgumentParser(description='Generate per-section Voynich call graphs')
    parser.add_argument('transcription', help='EVA transcription or compiled log file')
    parser.add_argument('--output-dir', default='voynich_graphs',
                        help='Directory for output files (default: voynich_graphs)')
    parser.add_argument('--animate', action='store_true',
                        help='Also render an MP4 animation (requires ffmpeg)')
    parser.add_argument('--min-nodes', type=int, default=5, metavar='N',
                        help='Skip folios with fewer than N nodes (default: 5)')
    parser.add_argument('--dpi', type=int, default=300)
    args = parser.parse_args()

    path = Path(args.transcription)
    source = compile_corpus(path) if 'ivtff' in path.name else path

    generate_sectional_graphs(
        source,
        output_dir=args.output_dir,
        animate=args.animate,
        min_nodes=args.min_nodes,
        dpi=args.dpi,
    )


if __name__ == '__main__':
    main()
