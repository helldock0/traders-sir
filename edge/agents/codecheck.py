"""Static and dynamic checks on a Builder-written strategy module before anyone trusts it."""
from __future__ import annotations

import ast
import importlib.util
import traceback
from pathlib import Path
from types import ModuleType

import numpy as np

from ..data import store
from ..engine.market import Market
from ..engine.strategy import Signals, run_signals
from ..research.leaktest import leak_report

FORBIDDEN_MODULES = {"os", "sys", "subprocess", "socket", "requests", "httpx", "urllib", "shutil", "pathlib", "pickle",
                     "random", "time", "datetime", "threading", "multiprocessing", "ctypes", "importlib", "builtins"}
ALLOWED_MODULES = {"numpy", "np", "polars", "pl", "math", "edge", "edge.engine", "edge.engine.features", "edge.engine.market",
                   "edge.engine.strategy", "typing", "dataclasses", "functools", "itertools", "collections", "__future__"}
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "print"}


def static_check(code: str, slug: str, params: dict, grid: dict) -> dict:
    issues: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"ok": False, "issues": [f"syntax error: {exc}"]}
    names_defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assigned = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for mname in mods:
                root = mname.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    issues.append(f"forbidden import: {mname}")
                elif mname not in ALLOWED_MODULES and root not in ALLOWED_MODULES:
                    issues.append(f"import not in the allow list: {mname}")
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if name in FORBIDDEN_CALLS:
                issues.append(f"forbidden call: {name}()")
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "np" and fn.attr in ("roll",):
                issues.append("np.roll wraps the array end to the start and is a classic look-ahead vector; use F.shift or explicit slicing")
    if "signals" not in names_defined:
        issues.append("no signals(m, p) function")
    if "PARAMS" not in assigned:
        issues.append("no PARAMS dict")
    if "NAME" not in assigned:
        issues.append("no NAME")
    return {"ok": not issues, "issues": issues}


def load_module_from_code(code: str, slug: str, folder: Path | None = None) -> tuple[ModuleType | None, Path, str | None]:
    folder = folder or (store.ROOT / "strategies" / "auto")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{slug}.py"
    path.write_text(code, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location(f"auto_{slug}", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod, path, None
    except Exception:
        return None, path, traceback.format_exc(limit=6)


def dynamic_check(mod: ModuleType, m: Market, params: dict, grid: dict, sample_bars: int = 150_000) -> dict:
    """Run signals on a slice, validate the Signals object, check parameter plumbing and leaks."""
    out: dict = {"ok": True, "issues": [], "entries": None, "leak": None}
    p = dict(getattr(mod, "PARAMS", {}))
    missing = [k for k in grid if k not in p]
    if missing:
        out["issues"].append(f"PARAMS lacks grid keys: {missing}")
    for k, v in params.items():
        if k in p and str(p[k]) != str(v):
            out["issues"].append(f"PARAMS[{k}] = {p[k]!r} but the spec default is {v!r}")
    sl = m.rows(max(0, m.n - sample_bars), m.n)
    try:
        sig = run_signals(mod, sl, None)
    except Exception:
        out["ok"] = False
        out["issues"].append("signals() raised:\n" + traceback.format_exc(limit=8))
        return out
    out["entries"] = int(sig.n_entries)
    if sig.n_entries == 0:
        out["issues"].append(f"no entries at all on the last {sl.n} bars of {m.sym}; check times, filters and sparse-bar handling")
    # parameter sensitivity: a grid value that changes nothing suggests the parameter is not wired
    for k, vals in grid.items():
        if k not in p or len(vals) < 2:
            continue
        alt = dict(p)
        alt[k] = vals[-1] if str(vals[-1]) != str(p[k]) else vals[0]
        try:
            sig2 = run_signals(mod, sl, alt)
        except Exception:
            out["issues"].append(f"signals() raised with {k}={alt[k]!r}:\n" + traceback.format_exc(limit=4))
            continue
        same = (np.array_equal(sig.entry_long, sig2.entry_long) and np.array_equal(sig.entry_short, sig2.entry_short)
                and np.array_equal(np.nan_to_num(sig.sl_dist), np.nan_to_num(sig2.sl_dist))
                and np.array_equal(np.nan_to_num(sig.tp_dist), np.nan_to_num(sig2.tp_dist))
                and np.array_equal(sig.exit_long, sig2.exit_long) and np.array_equal(sig.exit_short, sig2.exit_short))
        if same and sig.n_entries > 0:
            out["issues"].append(f"parameter {k} has no effect on the signals (value {p[k]!r} vs {alt[k]!r})")
    try:
        leak = leak_report(mod, sl, None)
        out["leak"] = leak
        if not leak["ok"]:
            out["ok"] = False
            out["issues"].append(f"leak tests failed: truncation ok={leak['truncation']['ok']} perturbation ok={leak['perturbation']['ok']} determinism ok={leak['determinism']['ok']}")
    except Exception:
        out["ok"] = False
        out["issues"].append("leak test raised:\n" + traceback.format_exc(limit=6))
    if any(i.startswith("PARAMS lacks") or "raised" in i for i in out["issues"]):
        out["ok"] = False
    return out


def full_check(code: str, slug: str, params: dict, grid: dict, m: Market) -> tuple[dict, ModuleType | None, Path | None]:
    st = static_check(code, slug, params, grid)
    result = {"static": st, "import": None, "dynamic": None, "ok": False}
    if not st["ok"]:
        return result, None, None
    mod, path, err = load_module_from_code(code, slug)
    result["import"] = {"ok": err is None, "error": err, "path": str(path)}
    if mod is None:
        return result, None, path
    dyn = dynamic_check(mod, m, params, grid)
    result["dynamic"] = dyn
    result["ok"] = dyn["ok"]
    return result, mod, path
