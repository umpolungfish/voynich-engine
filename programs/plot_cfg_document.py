"""
Document-quality CFG for f116r — tight layout, thick edges, opcode-family coloring.

Renders the largest connected component of f116r's register flow graph with:
  - k=0.03 spring layout (much denser than default 0.10)
  - edge width 2.2 (vs default 1.0), edge alpha 0.55
  - nodes color-coded by opcode family:
      blue   — Frobenius (FSPLIT / FFUSE)
      orange — Morphism  (AFWD / AREV / CLINK)
      green  — Identity / Linear (ISCRIB / IFIX)
      red    — Dialetheia (EVALT / EVALF / ENGAGR)
      gray   — Bootstrap  (VINIT / TANCH)
  - no node labels (too dense), no axes, dark background

Output: docs/f116r_callgraph_document.png  (3200×3200 px @ 300 dpi)
"""

from __future__ import annotations
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

from voynich_engine.compiler import compile_corpus, peak_folios
from voynich_engine.callgraph import build_graph, largest_component
from voynich_engine.primitives import PRIMITIVES

TRANSCRIPTION = root / "data" / "LSI_ivtff_0d.txt"
OUT = root / "docs" / "voynich_callgraph_document.png"

_MNEM = {v["opcode"]: v["mnemonic"] for v in PRIMITIVES.values()}

_FAMILY_COLOR: dict[str, str] = {
    "FSPLIT":  "#4e79a7",
    "FFUSE":   "#4e79a7",
    "AFWD":    "#f28e2b",
    "AREV":    "#f28e2b",
    "CLINK":   "#f28e2b",
    "ISCRIB":  "#59a14f",
    "IFIX":    "#59a14f",
    "EVALT":   "#e15759",
    "EVALF":   "#e15759",
    "ENGAGR":  "#e15759",
    "VINIT":   "#9c9c9c",
    "TANCH":   "#9c9c9c",
}
_DEFAULT_COLOR = "#cccccc"

_LEGEND_PATCHES = [
    mpatches.Patch(color="#4e79a7", label="Frobenius (FSPLIT / FFUSE)"),
    mpatches.Patch(color="#f28e2b", label="Morphism (AFWD / AREV / CLINK)"),
    mpatches.Patch(color="#59a14f", label="Identity / Linear (ISCRIB / IFIX)"),
    mpatches.Patch(color="#e15759", label="Dialetheia (EVALT / EVALF / ENGAGR)"),
    mpatches.Patch(color="#9c9c9c", label="Bootstrap (VINIT / TANCH)"),
]


def node_mnemonic(node_id: int, instructions: list[str]) -> str:
    for line in instructions:
        if f"%r{node_id}" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
    return ""


def main() -> None:
    print("Compiling corpus …")
    result = compile_corpus(TRANSCRIPTION)
    folios = result["folios"]
    top = peak_folios(result, 1)
    peak_name = top[0][0] if top else "full corpus"

    all_instructions: list[str] = []
    for folio_data in folios.values():
        all_instructions.extend(folio_data["instructions"])

    print(f"Folios: {len(folios)}  |  Instructions: {len(all_instructions)}")
    print(f"Peak folio by register count: {peak_name}")

    instructions = all_instructions
    G = build_graph(instructions)
    C = largest_component(G)
    print(f"Component: {C.number_of_nodes()} nodes, {C.number_of_edges()} edges")

    # Assign colors
    node_colors = []
    for n in C.nodes():
        mnem = node_mnemonic(n, instructions)
        node_colors.append(_FAMILY_COLOR.get(mnem, _DEFAULT_COLOR))

    # Spring layout — small k = tight clustering
    print("Computing layout (k=0.03, 300 iterations) …")
    pos = nx.spring_layout(C, k=0.03, iterations=300, seed=42)

    # Render
    fig, ax = plt.subplots(figsize=(14, 14), facecolor="#0d0d1a")
    ax.set_facecolor("#0d0d1a")

    # Split edges by label for styling
    split_edges = [(u, v) for u, v, d in C.edges(data=True) if d.get("label") == "split"]
    flow_edges  = [(u, v) for u, v, d in C.edges(data=True) if d.get("label") != "split"]

    nx.draw_networkx_edges(
        C, pos, edgelist=flow_edges, ax=ax,
        edge_color="#5588aa", alpha=0.45, width=1.6,
        arrows=True, arrowsize=6, arrowstyle="-|>",
        connectionstyle="arc3,rad=0.05",
        min_source_margin=4, min_target_margin=4,
    )
    nx.draw_networkx_edges(
        C, pos, edgelist=split_edges, ax=ax,
        edge_color="#f28e2b", alpha=0.65, width=2.8,
        arrows=True, arrowsize=8, arrowstyle="-|>",
        connectionstyle="arc3,rad=0.12",
        min_source_margin=4, min_target_margin=4,
    )
    nx.draw_networkx_nodes(
        C, pos, ax=ax,
        node_color=node_colors, node_size=22,
        linewidths=0.3, edgecolors="#ffffff33",
    )

    ax.set_axis_off()
    ax.set_title(
        f"Voynich Manuscript — IMASM Register Flow Graph (full corpus)\n"
        f"{C.number_of_nodes()} nodes · {C.number_of_edges()} edges · "
        f"{len(folios)} folios · largest component",
        color="white", fontsize=11, pad=12,
    )

    legend = ax.legend(
        handles=_LEGEND_PATCHES,
        loc="lower right", framealpha=0.3, facecolor="#1a1a2e",
        edgecolor="#444466", labelcolor="white", fontsize=8,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
