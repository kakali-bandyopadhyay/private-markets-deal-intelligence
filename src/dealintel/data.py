"""Load the synthetic corpus: documents (versioned), passages, tagged facts, companies, deals, thesis and metrics.

Facts are hand-tagged in this synthetic set. In real use an extraction step would propose them and a person would
confirm them; the prototype does not claim automated extraction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


# not evidence: the IC decision record (it points at the memo), model settings, value assumptions and every evaluation
# file - adding a question set must never change the memo fingerprint
NOT_EVIDENCE = frozenset({"ic_decisions.json", "model_config.json", "value_assumptions.json", "eval/"})


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(data_dir: Path = DATA, exclude: frozenset[str] = frozenset()) -> str:
    """SHA-256 over every data file, independent of line endings (Windows checkouts give the same value)."""
    h = hashlib.sha256()
    for p in sorted(data_dir.rglob("*.json")):
        rel = p.relative_to(data_dir).as_posix()
        if p.name in exclude or any(rel.startswith(x) for x in exclude if x.endswith("/")):
            continue
        h.update(p.relative_to(data_dir).as_posix().encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def load(data_dir: Path = DATA) -> dict:
    docs = {}
    for p in sorted((data_dir / "documents").glob("*.json")):
        d = _read(p)
        docs[d["key"]] = d
    passages, facts = {}, []
    for d in docs.values():
        for para in d["paragraphs"]:
            pid = f"{d['key']}#p{para['n']}"
            passages[pid] = {"id": pid, "doc": d["key"], "text": para["text"], "date": d["date"],
                             "deal": d["deal"], "company": d["company"],
                             "evidence_class": d["evidence_class"]}
            for i, f in enumerate(para["facts"], 1):
                facts.append({"id": f"{pid}/f{i}", "passage": pid, "doc": d["key"], "date": d["date"],
                              "company": f.get("company", d["company"]), "metric": f["metric"],
                              "value": f["value"], "period": f["period"], "basis": f.get("basis")})
    comp = _read(data_dir / "companies.json")["companies"]
    ctx = {
        "docs": docs, "passages": passages, "facts": facts,
        "companies": {c["id"]: c for c in comp},
        "deals": {d["id"]: d for d in _read(data_dir / "deals.json")["deals"]},
        "thesis": _read(data_dir / "thesis.json"),
        "metrics": _read(data_dir / "metrics.json"),
        "fingerprint": fingerprint(data_dir),
        # what the memo is built from: excludes the IC decision record (it points at the memo, not into it), the
        # evaluation set and the model settings
        "evidence_fingerprint": fingerprint(data_dir, NOT_EVIDENCE),
        "data_dir": data_dir,
    }
    for name in ("screening_decisions",):
        p = data_dir / f"{name}.json"
        ctx[name] = _read(p)["records"] if p.exists() else []
    _validate(ctx)
    return ctx


def _validate(ctx: dict) -> None:
    for d in ctx["docs"].values():
        if d["supersedes"] and d["supersedes"] not in ctx["docs"]:
            raise ValueError(f"{d['key']} supersedes unknown document {d['supersedes']}")
        if d["company"] and d["company"] not in ctx["companies"]:
            raise ValueError(f"{d['key']} refers to unknown company {d['company']}")
    for f in ctx["facts"]:
        if f["metric"] not in ctx["metrics"]:
            raise ValueError(f"fact {f['id']} uses unknown metric {f['metric']}")
        if f["value"] is None:
            raise ValueError(f"fact {f['id']} has no value")


def latest_date(ctx: dict) -> str:
    return max(d["date"] for d in ctx["docs"].values())


def active_docs(ctx: dict, as_of: str | None = None) -> set[str]:
    """Documents dated on or before as_of that no later version (also on or before as_of) supersedes."""
    as_of = as_of or latest_date(ctx)
    seen = {k for k, d in ctx["docs"].items() if d["date"] <= as_of}
    replaced = {ctx["docs"][k]["supersedes"] for k in seen if ctx["docs"][k]["supersedes"]}
    return seen - replaced


def active_facts(ctx: dict, company: str, as_of: str | None = None) -> list[dict]:
    live = active_docs(ctx, as_of)
    return [f for f in ctx["facts"] if f["company"] == company and f["doc"] in live]


def fmt(ctx: dict, metric: str, value) -> str:
    unit = ctx["metrics"][metric]["unit"]
    if unit == "%":
        return f"{value * 100:.0f}%" if abs(value * 100 - round(value * 100)) < 1e-9 else f"{value * 100:.1f}%"
    if unit == "EUR m":
        return f"EUR {value:g}m"
    if unit == "EUR bn":
        return f"EUR {value:g}bn"
    return str(value)
