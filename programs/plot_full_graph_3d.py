"""
Interactive 3D rotatable call graph for the full Voynich corpus.

Extracts the largest weakly connected component (546 nodes, 693 edges)
from the complete compiled instruction stream and renders it as a
rotatable 3D spring-embedded plot with an orbit button.

Also generates an orbit GIF at docs/voynich_callgraph_orbit.gif.

Output: docs/voynich_callgraph_3d.html, docs/voynich_callgraph_orbit.gif
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

TRANSCRIPTION = root / "data" / "LSI_ivtff_0d.txt"
OUT_HTML = root / "docs" / "voynich_callgraph_3d.html"
OUT_GIF  = root / "docs" / "voynich_callgraph_orbit.gif"

GIF_FRAMES   = 72    # one full orbit in 72 steps (5° each)
GIF_FPS      = 24
GIF_W, GIF_H = 1200, 900

# Camera orbit parameters: radius and z-height in Plotly scene units
ORBIT_RADIUS = 1.8
ORBIT_Z      = 1.2

# Mnemonic prefix → color
MNEM_COLORS = {
    "ID_SCR": "#4e79a7",   # identity — blue
    "ARW_FW": "#76b7b2",   # forward morphism — teal
    "ARW_RE": "#f28e2b",   # reverse morphism — orange
    "COMP_L": "#edc948",   # composition — yellow
    "FSPLIT": "#e15759",   # Frobenius split — red
    "FFUSE":  "#59a14f",   # Frobenius fuse — green
    "DIAL_T": "#9c755f",   # lattice true — brown
    "DIAL_F": "#bab0ac",   # lattice false — grey
    "DIAL_B": "#b07aa1",   # lattice both/paradox — purple
    "INS_FI": "#ff9da7",   # IFIX — pink
    "VOID_I": "#a0cbe8",   # void init — light blue
    "TERM_A": "#ffbe7d",   # terminal anchor — peach
}
DEFAULT_COLOR = "#aec7e8"


def node_label(node_id: int, instructions: list[str]) -> str:
    for line in instructions:
        if f"%r{node_id}" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
    return str(node_id)


def node_folio(node_id: int, folio_ranges: dict[str, tuple[int, int]]) -> str:
    for folio, (lo, hi) in folio_ranges.items():
        if lo <= node_id <= hi:
            return folio
    return "unknown"


def spring_layout_3d(G: nx.DiGraph, seed: int = 42, iterations: int = 300) -> dict:
    np.random.seed(seed)
    nodes = list(G.nodes())
    n = len(nodes)
    idx = {v: i for i, v in enumerate(nodes)}

    phi = np.random.uniform(0, 2 * np.pi, n)
    theta = np.arccos(np.random.uniform(-1, 1, n))
    pos = np.column_stack([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ]).astype(float)

    k = 1.0 / np.sqrt(n)
    for it in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=2) + 1e-8
        rep = (k**2 / dist**2)[:, :, None] * delta / dist[:, :, None]
        np.fill_diagonal(rep[:, :, 0], 0)
        np.fill_diagonal(rep[:, :, 1], 0)
        np.fill_diagonal(rep[:, :, 2], 0)
        disp = rep.sum(axis=1)
        for u, v in G.edges():
            i, j = idx[u], idx[v]
            d = dist[i, j]
            f = (d**2 / k) * delta[i, j] / d
            disp[i] -= f
            disp[j] += f
        mag = np.linalg.norm(disp, axis=1, keepdims=True) + 1e-8
        t = 0.15 * (1 - it / iterations)
        pos += disp / mag * np.minimum(mag, t)
        if it % 50 == 0:
            print(f"  layout {it}/{iterations}...")

    return {v: pos[idx[v]] for v in nodes}


def make_figure(G: nx.DiGraph, pos3d: dict, labels: dict, folio_hover: dict) -> go.Figure:
    # Edges
    edge_x, edge_y, edge_z = [], [], []
    split_ex, split_ey, split_ez = [], [], []
    for u, v, data in G.edges(data=True):
        x0, y0, z0 = pos3d[u]
        x1, y1, z1 = pos3d[v]
        if data.get("label") == "split":
            split_ex += [x0, x1, None]
            split_ey += [y0, y1, None]
            split_ez += [z0, z1, None]
        else:
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
            edge_z += [z0, z1, None]

    flow_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode="lines",
        line=dict(color="rgba(100,100,140,0.35)", width=1.5),
        hoverinfo="none", showlegend=False,
    )
    split_trace = go.Scatter3d(
        x=split_ex, y=split_ey, z=split_ez,
        mode="lines",
        line=dict(color="rgba(225,87,89,0.6)", width=2.5),
        hoverinfo="none", name="FSPLIT edges", showlegend=True,
    )

    # Nodes grouped by mnemonic for legend
    mnem_groups: dict[str, list] = {}
    for n in G.nodes():
        lbl = labels.get(n, "")
        short = lbl[:6]
        mnem_groups.setdefault(short, []).append(n)

    node_traces = []
    for short, nodes in sorted(mnem_groups.items()):
        color = MNEM_COLORS.get(short, DEFAULT_COLOR)
        nx_arr = [float(pos3d[n][0]) for n in nodes]
        ny_arr = [float(pos3d[n][1]) for n in nodes]
        nz_arr = [float(pos3d[n][2]) for n in nodes]
        hover = [f"r{n} | {labels.get(n,'')} | {folio_hover.get(n,'')}" for n in nodes]
        node_traces.append(go.Scatter3d(
            x=nx_arr, y=ny_arr, z=nz_arr,
            mode="markers",
            marker=dict(size=5, color=color, line=dict(color="rgba(255,255,255,0.3)", width=0.5)),
            hovertext=hover,
            hoverinfo="text",
            name=labels.get(nodes[0], short),
            legendgroup=short,
            showlegend=True,
        ))

    axis_style = dict(
        showgrid=False, zeroline=False, showticklabels=False, title="",
        backgroundcolor="#0d0d1a", showbackground=True,
        gridcolor="#1a1a2e", linecolor="#1a1a2e",
    )

    fig = go.Figure(data=[flow_trace, split_trace] + node_traces)
    fig.update_layout(
        title=dict(
            text=(
                "Voynich Manuscript — Full Corpus Call Graph (3D rotatable)<br>"
                "<sup>Largest weakly connected component · "
                f"{G.number_of_nodes()} nodes · {G.number_of_edges()} edges</sup>"
            ),
            font=dict(size=15, color="white"),
            x=0.5,
        ),
        paper_bgcolor="#0d0d1a",
        plot_bgcolor="#0d0d1a",
        scene=dict(
            xaxis=axis_style,
            yaxis=axis_style,
            zaxis=axis_style,
            bgcolor="#0d0d1a",
        ),
        legend=dict(
            font=dict(color="white", size=10),
            bgcolor="rgba(13,13,26,0.8)",
            bordercolor="#333",
            borderwidth=1,
        ),
        margin=dict(l=0, r=0, t=80, b=0),
        annotations=[dict(
            text=(
                "Node color = IMASM primitive · Red edges = FROB_SPLIT forks · "
                "Hover for register ID, mnemonic, and source folio"
            ),
            x=0.5, y=0.01, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=10, color="#7777aa"),
            align="center",
        )],
    )
    return fig


_ORBIT_JS = """
<style>
  #orbit-btn {
    position: fixed; top: 18px; right: 18px; z-index: 9999;
    background: rgba(13,13,26,0.85); color: #aaaacc;
    border: 1px solid #333355; border-radius: 6px;
    padding: 8px 18px; font-size: 14px; font-family: monospace;
    cursor: pointer; transition: background 0.2s;
  }
  #orbit-btn:hover { background: rgba(40,40,80,0.95); color: white; }
  #orbit-btn.active { color: #e15759; border-color: #e15759; }
</style>
<button id="orbit-btn" onclick="toggleOrbit()">&#9654; Orbit</button>
<script>
(function() {
  var orbiting = false;
  var raf = null;
  var angle = 0;

  window.toggleOrbit = function() {
    var btn = document.getElementById('orbit-btn');
    if (orbiting) {
      orbiting = false;
      if (raf) cancelAnimationFrame(raf);
      btn.innerHTML = '&#9654; Orbit';
      btn.classList.remove('active');
    } else {
      orbiting = true;
      btn.innerHTML = '&#9646;&#9646; Stop';
      btn.classList.add('active');

      // read current camera to get radius + z
      var plotDiv = document.querySelector('.plotly-graph-div');
      var cam = plotDiv._fullLayout.scene.camera;
      var ex = cam.eye.x, ey = cam.eye.y, ez = cam.eye.z;
      var r = Math.sqrt(ex * ex + ey * ey);
      if (r < 0.01) r = 1.8;   // fallback
      angle = Math.atan2(ey, ex);

      function step() {
        if (!orbiting) return;
        angle += 0.018;   // ~1°/frame at 60fps = ~6s per revolution
        Plotly.relayout(plotDiv, {
          'scene.camera.eye': {
            x: r * Math.cos(angle),
            y: r * Math.sin(angle),
            z: ez
          }
        });
        raf = requestAnimationFrame(step);
      }
      raf = requestAnimationFrame(step);
    }
  };
})();
</script>
"""


def inject_orbit_button(html: str) -> str:
    """Inject the orbit button + JS just before </body>."""
    return html.replace("</body>", _ORBIT_JS + "\n</body>")


def generate_gif(fig: go.Figure) -> None:
    """Render GIF_FRAMES frames orbiting at ORBIT_RADIUS/ORBIT_Z, save as GIF."""
    import imageio.v3 as iio
    from PIL import Image
    import io, tempfile

    print(f"Generating GIF ({GIF_FRAMES} frames at {GIF_W}×{GIF_H})...")
    frames = []
    for i in range(GIF_FRAMES):
        angle = 2 * np.pi * i / GIF_FRAMES
        fig.update_layout(scene_camera=dict(eye=dict(
            x=ORBIT_RADIUS * np.cos(angle),
            y=ORBIT_RADIUS * np.sin(angle),
            z=ORBIT_Z,
        )))
        png_bytes = fig.to_image(format="png", width=GIF_W, height=GIF_H, scale=1)
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        frames.append(np.array(img))
        if i % 12 == 0:
            print(f"  frame {i}/{GIF_FRAMES}")

    # Encode GIF with imageio (palette-quantised per frame)
    iio.imwrite(
        str(OUT_GIF),
        frames,
        format="gif",
        loop=0,                         # loop forever
        duration=int(1000 / GIF_FPS),   # ms per frame
    )
    print(f"GIF saved: {OUT_GIF}  ({OUT_GIF.stat().st_size // 1024} KB)")


def main():
    print("Compiling corpus...")
    result = compile_corpus(TRANSCRIPTION)
    print(f"Compiled {result['folio_count']} folios, {result['total_registers']} registers")

    # Build folio register ranges for hover labels
    folio_ranges: dict[str, tuple[int, int]] = {}
    offset = 0
    for folio, data in sorted(result["folios"].items()):
        count = data["registers"]
        if count:
            folio_ranges[folio] = (offset, offset + count - 1)
            offset += count

    # Flatten all instructions for label lookup
    all_instructions: list[str] = []
    for data in result["folios"].values():
        all_instructions.extend(data["instructions"])

    print("Building graph...")
    G_full = build_graph(all_instructions)
    C = largest_component(G_full)
    print(f"Largest component: {C.number_of_nodes()} nodes, {C.number_of_edges()} edges")

    labels = {n: node_label(n, all_instructions) for n in C.nodes()}
    folio_hover = {n: node_folio(n, folio_ranges) for n in C.nodes()}

    print("Computing 3D layout (this takes ~30s)...")
    pos3d = spring_layout_3d(C)

    print("Building figure...")
    fig = make_figure(C, pos3d, labels, folio_hover)

    # --- HTML with orbit button ---
    html = fig.to_html(include_plotlyjs="cdn", full_html=True, div_id="voynich-graph")
    html = inject_orbit_button(html)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"HTML saved: {OUT_HTML}")

    # --- Orbit GIF ---
    generate_gif(fig)


if __name__ == "__main__":
    main()
