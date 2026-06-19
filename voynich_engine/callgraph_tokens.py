"""
Decompressed-token CFG builder for IMASM instruction streams.

Operates at the REGISTER level (one node per instruction occurrence, exactly
like callgraph.py) but decompresses each token into its true semantic
out-edges instead of only the sequential flow edge.

  Nodes  = register IDs (%rN) — one per compiled instruction; same node set
            as callgraph.py, labelled with their mnemonic.

  Edges  = the sequential flow PLUS semantic fan-out per token type:

    FSPLIT  → next two regs        δ-split (already in callgraph.py)
    ENGAGR  → next reg             ∅  (empty  — ENGAGR sends nothing useful)
    ENGAGR  → next IMSCRIB          W  (weighted — paradox-weight to fountain)
    IMSCRIB  → next reg             src (normal flow)
    IMSCRIB  → next IFIX            ←  (backpop — IMSCRIB sole IFIX value path)
    CLINK   → next reg             ∘→id (annotated; NOT an IFIX edge)
    all others → next reg          flow

This produces SPLIT TRACES at every ENGAGR node (two outgoing edges of
different types) and a visible backpopulation arc from every IMSCRIB node.

Crown theorems visible in the graph:
  fountain_model           — every AFWD/AREV node is reachable only via IMSCRIB
  CLINK_to_IFIX_never_occurs — CLINK edges are typed ∘→id, never ∅/backpop
"""

from __future__ import annotations
import re
from collections import defaultdict

_INSTR_RE = re.compile(r'\s*0x[0-9a-fA-F]+\s*\|\s*(\w+)\s+%r(\d+)')

# ── Token family metadata ─────────────────────────────────────────────────────

TOKEN_FAMILY: dict[str, str] = {
    "IMSCRIB": "identity",
    "IFIX":   "identity",
    "AFWD":   "morphism",
    "AREV":   "morphism",
    "CLINK":  "morphism",
    "FSPLIT": "frobenius",
    "FFUSE":  "frobenius",
    "ENGAGR": "dialetheia",
    "EVALT":  "dialetheia",
    "EVALF":  "dialetheia",
    "VINIT":  "bootstrap",
    "TANCH":  "bootstrap",
}

TOKEN_COLOR: dict[str, str] = {
    "identity":   "#59a14f",
    "morphism":   "#f28e2b",
    "frobenius":  "#4e79a7",
    "dialetheia": "#e15759",
    "bootstrap":  "#9c9c9c",
}

# ── Semantic edge visual style ────────────────────────────────────────────────

EDGE_STYLE: dict[str, dict] = {
    "empty":    {"color": "#888888", "lw": 1.6, "alpha": 0.80, "style": "dashed"},
    "weighted": {"color": "#ffd700", "lw": 2.8, "alpha": 0.95, "style": "solid"},
    "backpop":  {"color": "#cc44ff", "lw": 2.8, "alpha": 0.95, "style": "solid"},
    "source":   {"color": "#f28e2b", "lw": 1.8, "alpha": 0.80, "style": "solid"},
    "frobenius":{"color": "#4e79a7", "lw": 2.2, "alpha": 0.85, "style": "solid"},
    "seq_clink":{"color": "#5588aa", "lw": 1.4, "alpha": 0.65, "style": "solid"},
    "flow":     {"color": "#3a5f80", "lw": 0.8, "alpha": 0.30, "style": "solid"},
}


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph(instructions: list[str]):
    """
    Build the decompressed-token register-level CFG.

    Each compiled instruction line becomes one node (register ID).
    Edges are typed by the semantic role of the source token:

      ENGAGR  : two out-edges — ∅ to next reg, W to next IMSCRIB
      IMSCRIB  : two out-edges — src to next reg, ← to next IFIX
      FSPLIT  : δ-split edges to next two regs
      CLINK   : ∘→id edge to next reg (never to IFIX)
      others  : standard flow edge to next reg

    Cross-instruction flow edge (last reg of instr i → first reg of instr i+1)
    is preserved as in callgraph.py.
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx required: uv add networkx")

    # ── Parse ──────────────────────────────────────────────────────────────
    parsed: list[tuple[int, str]] = []   # (reg_id, mnemonic)
    for line in instructions:
        m = _INSTR_RE.match(line)
        if m:
            parsed.append((int(m.group(2)), m.group(1)))

    if not parsed:
        return nx.DiGraph()

    # Build mnemonic→sorted positions for lookahead
    mnem_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for pos, (reg, mnem) in enumerate(parsed):
        mnem_positions[mnem].append((pos, reg))

    def next_reg_of(mnem: str, after_pos: int) -> int | None:
        for p, r in mnem_positions[mnem]:
            if p > after_pos:
                return r
        return None

    # ── Build graph ────────────────────────────────────────────────────────
    G: nx.DiGraph = nx.DiGraph()

    for reg, mnem in parsed:
        fam = TOKEN_FAMILY.get(mnem, "bootstrap")
        G.add_node(reg, mnemonic=mnem, family=fam,
                   color=TOKEN_COLOR.get(fam, "#cccccc"))

    for pos, (reg, mnem) in enumerate(parsed):
        next_pos = pos + 1
        next_reg = parsed[next_pos][0] if next_pos < len(parsed) else None

        if mnem == "FSPLIT":
            # δ-split: edge to next reg and the one after (co-multiplication)
            r1 = parsed[pos + 1][0] if pos + 1 < len(parsed) else None
            r2 = parsed[pos + 2][0] if pos + 2 < len(parsed) else None
            if r1 is not None:
                G.add_edge(reg, r1, etype="frobenius", label="δ")
            if r2 is not None:
                G.add_edge(reg, r2, etype="frobenius", label="δ")

        elif mnem == "ENGAGR":
            # ∅ edge to the sequential successor (usually IFIX)
            if next_reg is not None:
                G.add_edge(reg, next_reg, etype="empty", label="∅")
            # W edge to the next IMSCRIB in the stream — the split trace
            w_target = next_reg_of("IMSCRIB", pos)
            if w_target is not None and w_target != next_reg:
                G.add_edge(reg, w_target, etype="weighted", label="W")

        elif mnem == "IMSCRIB":
            # Normal source flow to next reg
            if next_reg is not None:
                G.add_edge(reg, next_reg, etype="source", label="src")
            # Backpopulation ← to the next IFIX in the stream
            bp_target = next_reg_of("IFIX", pos)
            if bp_target is not None and bp_target != next_reg:
                G.add_edge(reg, bp_target, etype="backpop", label="←")

        elif mnem == "CLINK":
            # ∘→id : never routes to IFIX
            if next_reg is not None:
                G.add_edge(reg, next_reg, etype="seq_clink", label="∘→id")

        else:
            if next_reg is not None:
                G.add_edge(reg, next_reg, etype="flow", label="")

    return G


def largest_component(G):
    import networkx as nx
    if G.number_of_nodes() == 0:
        return G
    cc = max(nx.weakly_connected_components(G), key=len)
    return G.subgraph(cc).copy()


def summary(G) -> str:
    from collections import Counter
    etype_counts = Counter(d.get("etype", "flow") for _, _, d in G.edges(data=True))
    mnem_counts  = Counter(d.get("mnemonic", "?") for _, d in G.nodes(data=True))
    top = mnem_counts.most_common(3)
    top_str = ", ".join(f"{m}×{c}" for m, c in top)
    edge_str = "  ".join(f"{et}:{n}" for et, n in sorted(etype_counts.items()))
    return (
        f"{G.number_of_nodes()} nodes | {G.number_of_edges()} edges | "
        f"top tokens: {top_str} | edges: {edge_str}"
    )
