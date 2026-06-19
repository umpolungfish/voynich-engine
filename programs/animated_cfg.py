"""
Animated IMASM CFG for Voynich Manuscript.

Two-phase animation:
  Phase 1 — progressive build: nodes and edges appear in instruction order,
             color-coded by opcode family.
  Phase 2 — flow wave: full graph revealed, a Gaussian pulse travels through
             nodes in execution order, pulsing size and brightness.

Renders frames directly to PIL Images, assembles into an animated GIF.
Output: docs/animated_cfg.gif  (or --folio / --all-folios flags)
"""

from __future__ import annotations
import argparse
import io
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx

from voynich_engine.compiler import compile_corpus, peak_folios
from voynich_engine.callgraph import build_graph, largest_component

TRANSCRIPTION = root / "data" / "LSI_ivtff_0d.txt"
OUT_DIR = root / "docs"

BG = "#0d0d1a"

_FAMILY_COLOR: dict[str, str] = {
    "FSPLIT": "#4e79a7",
    "FFUSE":  "#4e79a7",
    "AFWD":   "#f28e2b",
    "AREV":   "#f28e2b",
    "CLINK":  "#f28e2b",
    "IMSCRIB": "#59a14f",
    "IFIX":   "#59a14f",
    "EVALT":  "#e15759",
    "EVALF":  "#e15759",
    "ENGAGR": "#e15759",
    "VINIT":  "#9c9c9c",
    "TANCH":  "#9c9c9c",
}
_FROBENIUS = {"FSPLIT", "FFUSE"}


def parse_instructions(instructions: list[str]) -> list[tuple[int, str]]:
    result = []
    for line in instructions:
        m = re.match(r"\s*0x[0-9a-fA-F]+\s*\|\s*(\w+)\s+%r(\d+)", line)
        if m:
            result.append((int(m.group(2)), m.group(1)))
    return result


def render_frame(
    ax: plt.Axes,
    all_nodes: list[int],
    pos: dict,
    edges: list,
    mnem_map: dict[int, str],
    base_colors: np.ndarray,
    revealed: set[int] | None,
    pulse_center: int | None,
    pulse_sigma: int,
    N: int,
) -> None:
    ax.clear()
    ax.set_facecolor(BG)
    ax.set_axis_off()
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)

    xs = np.array([pos[n][0] for n in all_nodes])
    ys = np.array([pos[n][1] for n in all_nodes])

    if revealed is not None:
        # Phase 1: build
        vis = [n in revealed for n in all_nodes]
        vis_idx = [i for i, v in enumerate(vis) if v]
        if not vis_idx:
            return

        # Draw edges
        for u, v, d in edges:
            if u in revealed and v in revealed:
                lw  = 2.0 if (mnem_map.get(u,"") in _FROBENIUS or mnem_map.get(v,"") in _FROBENIUS) else 0.9
                col = "#f28e2b" if lw > 1.5 else "#3a5f80"
                al  = 0.7 if lw > 1.5 else 0.35
                ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                        color=col, lw=lw, alpha=al, zorder=1)

        cx = xs[[i for i in vis_idx]]
        cy = ys[[i for i in vis_idx]]
        cc = base_colors[vis_idx]
        ax.scatter(cx, cy, c=cc, s=18, zorder=3, linewidths=0)

    else:
        # Phase 2: flow wave
        dists = np.abs(np.arange(N) - pulse_center)
        dists = np.minimum(dists, N - dists)
        weights = np.exp(-0.5 * (dists / pulse_sigma) ** 2)

        pulse_rgba = np.array(mcolors.to_rgba("#ffffff"))
        blended = base_colors * (1 - weights[:, None]) + pulse_rgba * weights[:, None]
        blended = np.clip(blended, 0, 1)
        sizes = 18 + 32 * weights

        # Draw all edges
        for u, v, d in edges:
            lw  = 2.0 if (mnem_map.get(u,"") in _FROBENIUS or mnem_map.get(v,"") in _FROBENIUS) else 0.9
            col = "#f28e2b" if lw > 1.5 else "#3a5f80"
            al  = 0.65 if lw > 1.5 else 0.30
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=col, lw=lw, alpha=al, zorder=1)

        ax.scatter(xs, ys, c=blended, s=sizes, zorder=3, linewidths=0)


def fig_to_pil(fig: plt.Figure, dpi: int) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=BG, bbox_inches="tight")
    buf.seek(0)
    return Image.open(buf).copy()


def build_animation(
    folio_name: str,
    instructions: list[str],
    out_path: Path,
    build_frames: int = 50,
    flow_frames: int = 80,
    fps: int = 15,
    dpi: int = 100,
    figsize: tuple[float, float] = (8, 8),
) -> None:
    parsed = parse_instructions(instructions)
    if not parsed:
        print(f"  No parseable instructions in {folio_name}.")
        return

    G = build_graph(instructions)
    C = largest_component(G)

    node_order: list[int] = []
    seen: set[int] = set()
    for r, _ in parsed:
        if r in C.nodes() and r not in seen:
            node_order.append(r)
            seen.add(r)

    N = len(node_order)
    if N == 0:
        print(f"  No nodes in largest component for {folio_name}.")
        return

    mnem_map: dict[int, str] = {r: m for r, m in parsed}
    edges = list(C.edges(data=True))

    print(f"  Layout ({N} nodes, {C.number_of_edges()} edges) …")
    pos = nx.spring_layout(C, k=0.04, iterations=250, seed=42)

    base_colors = np.array([
        mcolors.to_rgba(_FAMILY_COLOR.get(mnem_map.get(n, ""), "#cccccc"))
        for n in node_order
    ])

    pulse_sigma = max(6, N // 18)
    pulse_centers = np.linspace(0, N - 1, flow_frames).astype(int)

    total_frames = build_frames + flow_frames
    print(f"  Rendering {total_frames} frames …")

    fig, ax = plt.subplots(figsize=figsize, facecolor=BG)
    ax.set_facecolor(BG)

    frames_pil: list[Image.Image] = []

    for f in range(total_frames):
        pct = (f + 1) / total_frames * 100
        print(f"\r  {pct:5.1f}%  frame {f+1}/{total_frames}", end="", flush=True)

        if f < build_frames:
            frac = (f + 1) / build_frames
            k = max(1, int(frac * N))
            revealed = set(node_order[:k])
            render_frame(ax, node_order, pos, edges, mnem_map,
                         base_colors, revealed, None, pulse_sigma, N)
        else:
            fi = f - build_frames
            render_frame(ax, node_order, pos, edges, mnem_map,
                         base_colors, None, pulse_centers[fi], pulse_sigma, N)

        ax.set_title(
            f"Voynich — {folio_name}  |  IMASM Register Flow  |  {N} nodes  |  "
            f"{'build' if f < build_frames else 'flow'}",
            color="white", fontsize=8, pad=6,
        )

        frames_pil.append(fig_to_pil(fig, dpi))

    print()
    plt.close(fig)

    # Quantize all frames to palette for efficient GIF
    duration_ms = 1000 // fps
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Assembling GIF → {out_path} …")
    frames_rgb = [f.convert("RGB") for f in frames_pil]
    frames_rgb[0].save(
        str(out_path),
        save_all=True,
        append_images=frames_rgb[1:],
        duration=duration_ms,
        loop=0,
        optimize=False,
    )
    sz = out_path.stat().st_size / (1024 * 1024)
    print(f"  Done: {out_path}  ({sz:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Animated IMASM CFG for Voynich corpus.")
    ap.add_argument("--folio", default=None,
                    help="Folio name (e.g. f103r). Default: top folio by register count.")
    ap.add_argument("--all-folios", action="store_true",
                    help="Generate one GIF per folio into docs/animated_cfg/.")
    ap.add_argument("--build-frames", type=int, default=50)
    ap.add_argument("--flow-frames",  type=int, default=80)
    ap.add_argument("--fps",  type=int, default=15)
    ap.add_argument("--dpi",  type=int, default=100)
    args = ap.parse_args()

    print("Compiling corpus …")
    result = compile_corpus(TRANSCRIPTION)
    folios = result["folios"]

    if args.all_folios:
        targets = [(name, folios[name]["instructions"]) for name in folios]
        out_base = OUT_DIR / "animated_cfg"
        out_base.mkdir(parents=True, exist_ok=True)
    elif args.folio:
        if args.folio not in folios:
            sys.exit(f"Folio '{args.folio}' not found.")
        targets = [(args.folio, folios[args.folio]["instructions"])]
        out_base = OUT_DIR
    else:
        top = peak_folios(result, 1)
        name = top[0][0] if top else list(folios)[0]
        targets = [(name, folios[name]["instructions"])]
        out_base = OUT_DIR

    for folio_name, instructions in targets:
        suffix = f"_{folio_name}" if args.all_folios else ""
        out_path = out_base / f"animated_cfg{suffix}.gif"
        print(f"\n[{folio_name}] {len(instructions)} instructions")
        build_animation(
            folio_name, instructions, out_path,
            build_frames=args.build_frames,
            flow_frames=args.flow_frames,
            fps=args.fps,
            dpi=args.dpi,
        )

    print("\nAll done.")


if __name__ == "__main__":
    main()
