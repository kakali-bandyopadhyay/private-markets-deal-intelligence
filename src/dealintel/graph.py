"""Knowledge graph over the corpus.

Nodes: company, attribute, deal, document version, passage, fact, metric (memo claims are added by the memo step).
Edges: DEAL_FOR, ABOUT, IN_DEAL, SUPERSEDES, PART_OF, SOURCED_FROM, MEASURES, DESCRIBES, HAS_ATTR (CITES, DEPENDS_ON).

What the graph adds over search: questions that need linked entities or version history -
  1. what changed between versions / dates (SUPERSEDES + fact values),
  2. which memo claims depend on a conflicted fact (DEPENDS_ON + conflicts),
  3. which companies are comparable through shared linked attributes (HAS_ATTR).
Finding a passage that answers a question is plain keyword search (search.py), not a graph feature.
"""
from __future__ import annotations

from .data import active_facts, fmt

ATTR_WEIGHTS = {"end_market": 3, "subsector": 2, "business_model": 2, "sector": 1, "customer_segment": 1, "region": 1}


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []

    def node(self, nid: str, kind: str, **attrs) -> None:
        self.nodes.setdefault(nid, {"kind": kind, **attrs})

    def edge(self, src: str, rel: str, dst: str) -> None:
        self.edges.append((src, rel, dst))

    def out(self, nid: str, rel: str) -> list[str]:
        return [d for s, r, d in self.edges if s == nid and r == rel]

    def into(self, nid: str, rel: str) -> list[str]:
        return [s for s, r, d in self.edges if d == nid and r == rel]

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for n in self.nodes.values():
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        rels: dict[str, int] = {}
        for _, r, _ in self.edges:
            rels[r] = rels.get(r, 0) + 1
        return {"nodes": kinds, "edges": rels}


def build(ctx: dict) -> Graph:
    g = Graph()
    for c in ctx["companies"].values():
        g.node(c["id"], "company", name=c["code_name"])
        for a in ATTR_WEIGHTS:
            aid = f"{a}:{c[a]}"
            g.node(aid, "attribute", field=a, value=c[a])
            g.edge(c["id"], "HAS_ATTR", aid)
    for d in ctx["deals"].values():
        g.node(d["id"], "deal", name=d["name"], stage=d["stage"])
        g.edge(d["id"], "DEAL_FOR", d["company"])
    for k, d in ctx["docs"].items():
        g.node(k, "document", title=d["title"], date=d["date"], version=d["version"])
        if d["company"]:
            g.edge(k, "ABOUT", d["company"])
        if d["deal"]:
            g.edge(k, "IN_DEAL", d["deal"])
        if d["supersedes"]:
            g.edge(k, "SUPERSEDES", d["supersedes"])
    for pid, p in ctx["passages"].items():
        g.node(pid, "passage")
        g.edge(pid, "PART_OF", p["doc"])
    for m in ctx["metrics"]:
        g.node(f"metric:{m}", "metric", name=ctx["metrics"][m]["name"])
    for f in ctx["facts"]:
        g.node(f["id"], "fact", metric=f["metric"], value=f["value"], period=f["period"])
        g.edge(f["id"], "SOURCED_FROM", f["passage"])
        g.edge(f["id"], "MEASURES", f"metric:{f['metric']}")
        g.edge(f["id"], "DESCRIBES", f["company"])
    return g


def lineage(ctx: dict, g: Graph, fact_id: str) -> list[str]:
    """fact -> passage -> document (-> the version it replaced) -> deal -> company."""
    if fact_id not in g.nodes:
        raise KeyError(f"unknown fact {fact_id}")
    f = g.nodes[fact_id]
    pid = g.out(fact_id, "SOURCED_FROM")[0]
    doc = g.out(pid, "PART_OF")[0]
    d = ctx["docs"][doc]
    steps = [f"fact {fact_id}: {ctx['metrics'][f['metric']]['name']} {fmt(ctx, f['metric'], f['value'])} ({f['period']})",
             f"passage {pid}: \"{ctx['passages'][pid]['text']}\"",
             f"document {doc}: {d['title']}, {d['author_role']}, {d['date']}"]
    for old in g.out(doc, "SUPERSEDES"):
        steps.append(f"replaces {old} ({ctx['docs'][old]['date']})")
    later = g.into(doc, "SUPERSEDES")
    if later:
        steps.append(f"replaced by {', '.join(later)}")
    for deal in g.out(doc, "IN_DEAL"):
        steps.append(f"deal {deal}: {ctx['deals'][deal]['name']}")
    cid = g.out(fact_id, "DESCRIBES")[0]
    steps.append(f"company {cid}: {ctx['companies'][cid]['code_name']}")
    return steps


def version_diff(ctx: dict, old_key: str, new_key: str) -> list[dict]:
    """Fact-level differences between two versions of a document."""
    def by_metric(key: str) -> dict:
        return {(f["metric"], f["period"]): f for f in ctx["facts"] if f["doc"] == key}
    a, b = by_metric(old_key), by_metric(new_key)
    out = []
    for k in sorted(set(a) | set(b)):
        fa, fb = a.get(k), b.get(k)
        if fa and fb and fa["value"] == fb["value"]:
            continue
        out.append({"metric": k[0], "period": k[1],
                    "old": fa and {"value": fa["value"], "passage": fa["passage"], "basis": fa["basis"]},
                    "new": fb and {"value": fb["value"], "passage": fb["passage"], "basis": fb["basis"]}})
    return out


def changes(ctx: dict, company: str, date_from: str, date_to: str) -> list[dict]:
    """What the live evidence says about a company at two dates, metric by metric."""
    def view(as_of: str) -> dict:
        v: dict[tuple, list] = {}
        for f in active_facts(ctx, company, as_of):
            v.setdefault((f["metric"], f["period"]), []).append(f)
        return v
    a, b = view(date_from), view(date_to)
    out = []
    for k in sorted(set(a) | set(b)):
        va = sorted((f["value"], f["passage"]) for f in a.get(k, []))
        vb = sorted((f["value"], f["passage"]) for f in b.get(k, []))
        if [x for x, _ in va] == [x for x, _ in vb]:
            continue  # same values, possibly from a newer version of the same document
        gone = [p for _, p in va if p not in {q for _, q in vb}]
        reason = []
        if not va:
            reason.append("new evidence")
        if gone:
            reason.append("superseded: " + ", ".join(gone))
        if len({x for x, _ in vb}) > 1:
            reason.append("sources now disagree")
        out.append({"metric": k[0], "period": k[1],
                    "before": [{"value": x, "passage": p} for x, p in va],
                    "after": [{"value": x, "passage": p} for x, p in vb],
                    "why": "; ".join(reason) or "value changed"})
    return out


def comparables(ctx: dict, g: Graph, company: str, k: int = 5) -> list[dict]:
    """Rank other companies by shared linked attributes, plus a revenue band from sourced facts."""
    mine = set(g.out(company, "HAS_ATTR"))
    rev = {f["company"]: f for f in ctx["facts"] if f["metric"] == "revenue_eur_m"}
    base = active_facts(ctx, company)
    base_rev = next((f for f in base if f["metric"] == "revenue_eur_m"), None)
    out = []
    for other in ctx["companies"]:
        if other == company:
            continue
        shared = sorted(mine & set(g.out(other, "HAS_ATTR")), key=lambda a: -ATTR_WEIGHTS[a.split(":")[0]])
        score = sum(ATTR_WEIGHTS[a.split(":")[0]] for a in shared)
        why = [a.replace(":", " = ") for a in shared]
        r = rev.get(other)
        if base_rev and r and 0.5 <= r["value"] / base_rev["value"] <= 2.0:
            score += 1
            why.append(f"revenue EUR {r['value']:g}m within 0.5-2x of EUR {base_rev['value']:g}m ({r['passage']})")
        if score:
            out.append({"company": other, "name": ctx["companies"][other]["code_name"], "score": score, "why": why})
    out.sort(key=lambda x: (-x["score"], x["company"]))
    return out[:k]


def claims_on_conflicts(g: Graph, conflict_facts: dict[str, list[str]]) -> dict[str, list[str]]:
    """For each conflict, the memo claims that depend on one of its facts (needs DEPENDS_ON edges from the memo step)."""
    return {cid: sorted({c for f in facts for c in g.into(f, "DEPENDS_ON")}) for cid, facts in conflict_facts.items()}
