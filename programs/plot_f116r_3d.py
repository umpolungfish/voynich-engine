"""
Interactive 3D rotatable call graph for folio f116r.

The bootstrap terminus folio produces a single closed loop:
  ID_SCRIBE → ARROW_REV → FROB_SPLIT → ARROW_FWD →
  FROB_FUSE → COMP_LINK → INS_FIX → (back to ID_SCRIBE)

Layout: 3D spring embedding via networkx + scipy, rendered with Plotly.
Output: docs/f116r_callgraph_3d.html
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import networkx as nx
import numpy as np
import plotly.graph_objects as go

from voynich_engine.compiler import compile_corpus
from voynich_engine.callgraph import build_graph, largest_component
from voynich_engine.primitives import PRIMITIVES

TRANSCRIPTION = root / "data" / "LSI_ivtff_0d.txt"
OUT = root / "docs" / "f116r_callgraph_3d.html"

# Opcode → mnemonic lookup
_OPCODE_TO_MNEM = {v["opcode"]: v["mnemonic"] for v in PRIMITIVES.values()}

def node_label(node_id: int, instructions: list[str]) -> str:
    """Find the mnemonic for a register node."""
    for line in instructions:
        if f"%r{node_id}" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
    return str(node_id)


def spring_layout_3d(G: nx.DiGraph, seed: int = 42) -> dict[int, np.ndarray]:
    """3D spring layout using networkx spectral seed + scipy minimizer."""
    import numpy as np

    np.random.seed(seed)
    nodes = list(G.nodes())
    n = len(nodes)
    idx = {v: i for i, v in enumerate(nodes)}

    # Initialize on a sphere
    phi = np.random.uniform(0, 2 * np.pi, n)
    theta = np.arccos(np.random.uniform(-1, 1, n))
    pos = np.column_stack([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ]).astype(float)

    # Fruchterman-Reingold in 3D
    k = 1.0 / np.sqrt(n) if n > 0 else 1.0
    for _ in range(200):
        delta = pos[:, None, :] - pos[None, :, :]          # (n,n,3)
        dist = np.linalg.norm(delta, axis=2) + 1e-8        # (n,n)
        # Repulsion
        rep = (k**2 / dist**2)[:, :, None] * delta / dist[:, :, None]
        np.fill_diagonal(rep[:, :, 0], 0)
        np.fill_diagonal(rep[:, :, 1], 0)
        np.fill_diagonal(rep[:, :, 2], 0)
        disp = rep.sum(axis=1)
        # Attraction
        for u, v in G.edges():
            i, j = idx[u], idx[v]
            d = dist[i, j]
            f = (d**2 / k) * delta[i, j] / d
            disp[i] -= f
            disp[j] += f
        # Move
        mag = np.linalg.norm(disp, axis=1, keepdims=True) + 1e-8
        t = 0.1 * (1 - _ / 200)
        pos += disp / mag * np.minimum(mag, t)

    return {v: pos[idx[v]] for v in nodes}


def make_figure(G: nx.DiGraph, pos3d: dict, labels: dict[int, str]) -> go.Figure:
    # Edge traces
    edge_x, edge_y, edge_z = [], [], []
    for u, v in G.edges():
        x0, y0, z0 = pos3d[u]
        x1, y1, z1 = pos3d[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_z += [z0, z1, None]

    edge_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode="lines",
        line=dict(color="rgba(120,120,120,0.5)", width=2),
        hoverinfo="none",
        name="flow",
        showlegend=False,
    )

    # Arrow cones at midpoints
    cone_x, cone_y, cone_z = [], [], []
    cone_u, cone_v_c, cone_w = [], [], []
    for u, v in G.edges():
        p0 = np.array(pos3d[u])
        p1 = np.array(pos3d[v])
        mid = (p0 + p1) / 2
        d = p1 - p0
        cone_x.append(float(mid[0]))
        cone_y.append(float(mid[1]))
        cone_z.append(float(mid[2]))
        cone_u.append(float(d[0]))
        cone_v_c.append(float(d[1]))
        cone_w.append(float(d[2]))

    arrow_trace = go.Cone(
        x=cone_x, y=cone_y, z=cone_z,
        u=cone_u, v=cone_v_c, w=cone_w,
        sizemode="absolute", sizeref=0.08,
        colorscale=[[0, "steelblue"], [1, "steelblue"]],
        showscale=False,
        hoverinfo="none",
        name="direction",
        showlegend=False,
    )

    # Color nodes by mnemonic
    mnem_colors = {
        "ID_SCR": "#4e79a7",
        "ARW_RE": "#f28e2b",
        "FSPLIT": "#e15759",
        "ARW_FW": "#76b7b2",
        "FFUSE":  "#59a14f",
        "COMP_L": "#edc948",
        "INS_FI": "#b07aa1",
    }
    node_colors = []
    node_text = []
    node_x, node_y, node_z = [], [], []
    for n in G.nodes():
        p = pos3d[n]
        node_x.append(float(p[0]))
        node_y.append(float(p[1]))
        node_z.append(float(p[2]))
        lbl = labels.get(n, str(n))
        short = lbl[:6]
        node_colors.append(mnem_colors.get(short, "#aec7e8"))
        node_text.append(f"r{n}<br>{lbl}")

    node_trace = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode="markers+text",
        marker=dict(size=10, color=node_colors, line=dict(color="white", width=1)),
        text=[labels.get(n, str(n)) for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=9, color="white"),
        hovertext=node_text,
        hoverinfo="text",
        name="registers",
    )

    fig = go.Figure(data=[edge_trace, arrow_trace, node_trace])
    fig.update_layout(
        title=dict(
            text="f116r — Bootstrap Terminus: Closed Loop Call Graph (3D rotatable)",
            font=dict(size=16, color="white"),
            x=0.5,
        ),
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        scene=dict(
            xaxis=dict(
                showgrid=False, zeroline=False, showticklabels=False, title="",
                backgroundcolor="#0d0d1a", showbackground=True,
                gridcolor="#1a1a2e", linecolor="#1a1a2e",
            ),
            yaxis=dict(
                showgrid=False, zeroline=False, showticklabels=False, title="",
                backgroundcolor="#0d0d1a", showbackground=True,
                gridcolor="#1a1a2e", linecolor="#1a1a2e",
            ),
            zaxis=dict(
                showgrid=False, zeroline=False, showticklabels=False, title="",
                backgroundcolor="#0d0d1a", showbackground=True,
                gridcolor="#1a1a2e", linecolor="#1a1a2e",
            ),
            bgcolor="#0d0d1a",
        ),
        margin=dict(l=0, r=0, t=60, b=0),
        legend=dict(font=dict(color="white")),
        annotations=[dict(
            text=(
                "s·a·ch·e·sh·d·y·s  —  "
                "ID_SCRIBE → ARROW_REV → FROB_SPLIT → ARROW_FWD → "
                "FROB_FUSE → COMP_LINK → INS_FIX → (loop)"
            ),
            x=0.5, y=0.02, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=11, color="#aaaacc"),
            align="center",
        )],
    )
    return fig


def main():
    print("Compiling corpus...")
    result = compile_corpus(TRANSCRIPTION)
    folio = result["folios"].get("f116r")
    if folio is None:
        print("ERROR: f116r not found in corpus")
        return

    instructions = folio["instructions"]
    print(f"f116r: {folio['registers']} registers, {len(instructions)} instructions")

    G = build_graph(instructions)
    C = largest_component(G)
    print(f"Graph: {C.number_of_nodes()} nodes, {C.number_of_edges()} edges")

    labels = {n: node_label(n, instructions) for n in C.nodes()}
    pos3d = spring_layout_3d(C)

    fig = make_figure(C, pos3d, labels)
    fig.write_html(str(OUT), include_plotlyjs="cdn", full_html=True)
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
