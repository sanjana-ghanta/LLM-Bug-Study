import csv, json, os, collections, math
BASE = (os.environ.get("LLM_BUG_STUDY_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__", os.path.join(os.getcwd(), "scripts", "analysis", "x")))), "..", "..")))
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
LANGS = {
    "java":   dict(data="data/bugs",   res="results/java",   five="results_fivetier_{m}.csv",
                   p6="results_exp6_bugid_recall_{m}.csv",        p7="results_exp7_context_framing_{m}.csv"),
    "python": dict(data="data/pybugs", res="results/python", five="results_fivetier_python_{m}.csv",
                   p6="results_exp6_bugid_recall_python_{m}.csv", p7="results_exp7_context_framing_python_{m}.csv"),
}
TRUE = ("true", "1", "yes", "y")


import json as _json, os as _os
_TL = {}
_p = _os.path.join((os.environ.get("LLM_BUG_STUDY_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__", os.path.join(os.getcwd(), "scripts", "analysis", "x")))), "..", ".."))), "results", "python", "true_bug_lines.json")
if _os.path.exists(_p):
    _TL = _json.load(open(_p))

def actual(r):
    """Ground-truth bug line. Python bugs use the corrected first-changed line
    (the stored one is the diff hunk start, 3 context lines early); Java unchanged."""
    k = f"{r['project']}_{r['bug_id']}"
    return _TL[k]["true"] if k in _TL else r["actual_line"]


def usable_set(dirn):
    s = set()
    for d in sorted(os.listdir(os.path.join(BASE, dirn))):
        p = os.path.join(BASE, dirn, d, "data.json")
        if not os.path.exists(p): continue
        j = json.load(open(p))
        if j.get("original_bug_line") is None: continue
        s.add((j.get("project", d.rsplit("_", 1)[0]), str(j.get("bug_id", d.rsplit("_", 1)[-1]))))
    return s

def rd(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else None

def load_five(path, usable, raw):
    first, drop, dups = {}, 0, 0
    for r in rd(path) or []:
        raw[r["correct"]] += 1
        k = (r["project"], str(r["bug_id"]), r["tier"])
        if (k[0], k[1]) not in usable: drop += 1; continue
        if k in first: dups += 1; continue
        first[k] = r["correct"].strip().lower() in TRUE
    return first, drop, dups

def pct(a, b): return f"{100*a/b:.1f}%" if b else "n/a"

def mcnemar_p(b, c):
    n = b + c
    if n == 0: return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

def to_int(x):
    try: return int(float(x))
    except Exception: return None

raw = collections.Counter()
for lang, cfg in LANGS.items():
    U = usable_set(cfg["data"])
    print("=" * 78); print(f"{lang.upper()}  usable bugs: {len(U)}"); print("=" * 78)
    data = {}
    for m in MODELS:
        first, drop, dups = load_five(os.path.join(BASE, cfg["res"], cfg["five"].format(m=m)), U, raw)
        data[m] = first
        print(f"{m}: unique usable rows {len(first)} | dropped (not usable) {drop} | duplicates removed {dups}")
    print("\n-- Stage 1 (baselines) and Stage 2 (gated), earliest row kept --")
    print(f"{'model':<28}{'T1 n':>6}{'T1 acc':>8}{'T2 n':>6}{'T2 acc':>8}{'bal':>8}{'T3 n':>6}{'T3 acc':>8}{'T3 excl':>8}{'T4 n':>6}{'T4 acc':>8}{'T4 excl':>8}")
    for m in MODELS:
        d = data[m]
        t1 = [v for k, v in d.items() if k[2] == "1"]; t2 = [v for k, v in d.items() if k[2] == "2"]
        c1, c2 = sum(t1), sum(t2)
        def gated(tier, pre):
            ev = [v for k, v in d.items() if k[2] == tier and d.get((k[0], k[1], pre)) is True]
            allr = [k for k in d if k[2] == tier]
            return len(ev), sum(ev), len(allr) - len(ev)
        n3, c3, x3 = gated("3", "1")
        _wp = os.path.join(BASE, cfg["res"], cfg["five"].format(m=m)).replace(".csv", "__t5-claude-sonnet-win.csv")
        _w = load_five(_wp, U, collections.Counter())[0] if os.path.exists(_wp) else {}
        _ev = [v for k, v in _w.items() if k[2] == "5" and d.get((k[0], k[1], "2")) is True]
        n5, c5 = len(_ev), sum(_ev); x5 = sum(1 for k in _w if k[2] == "5") - n5
        bal = (c1/len(t1) + c2/len(t2))/2*100 if t1 and t2 else float("nan")
        print(f"{m:<28}{len(t1):>6}{pct(c1,len(t1)):>8}{len(t2):>6}{pct(c2,len(t2)):>8}{bal:>7.1f}%{n3:>6}{pct(c3,n3):>8}{x3:>8}{n5:>6}{pct(c5,n5):>8}{x5:>8}")
    common = {(p, b) for (p, b) in U if all(((p, b, "1") in data[m] and (p, b, "2") in data[m]) for m in MODELS)}
    print(f"\n-- Common set: bugs all three models finished on T1 and T2 (n={len(common)}) --")
    for m in MODELS:
        a1 = [data[m][(p, b, "1")] for p, b in common]; a2 = [data[m][(p, b, "2")] for p, b in common]
        print(f"{m:<28} T1 {pct(sum(a1),len(a1)):>7}   T2 {pct(sum(a2),len(a2)):>7}   bal {((sum(a1)+sum(a2))/(2*len(a1))*100 if a1 else float('nan')):.1f}%")
    print("\n-- Probes (T2 = real buggy code; exact line (Python: corrected true line) vs old +-5; earliest row, usable bugs) --")
    for m in MODELS:
        P = {}
        for tag in ("p6", "p7"):
            rows = rd(os.path.join(BASE, cfg["res"], cfg[tag].format(m=m)))
            if rows is None: continue
            first = {}
            for r in rows:
                k = (r["project"], str(r["bug_id"]), r["tier"])
                if (k[0], k[1]) in U and k not in first: first[k] = r
            P[tag] = first
        for tag, name in (("p6", "Exp6 bug-ID"), ("p7", "Exp7 context")):
            if tag not in P: print(f"{m:<28}{name:<14} (no file)"); continue
            t2 = [r for k, r in P[tag].items() if k[2] == "2"]; t1 = [r for k, r in P[tag].items() if k[2] == "1"]
            ex = w5 = 0
            for r in t2:
                a, b = to_int(r["reported_line"]), to_int(actual(r))
                if a is not None and b is not None:
                    ex += a == b; w5 += abs(a - b) <= 5
            fa = sum(to_int(r["reported_line"]) is not None for r in t1)
            print(f"{m:<28}{name:<14} T2 n={len(t2):>3} exact={ex:>3} ({pct(ex,len(t2))}) +-5={w5:>3} ({pct(w5,len(t2))}) | T1 n={len(t1):>3} gave a line={fa:>3} ({pct(fa,len(t1))})")
        if "p6" in P and "p7" in P:
            keys = [k for k in P["p6"] if k[2] == "2" and k in P["p7"]]
            def hit(r):
                a, b = to_int(r["reported_line"]), to_int(actual(r)); return a is not None and b is not None and a == b
            b6 = sum(hit(P["p6"][k]) and not hit(P["p7"][k]) for k in keys)
            c7 = sum(hit(P["p7"][k]) and not hit(P["p6"][k]) for k in keys)
            print(f"{'':<28}paired T2 bugs={len(keys)}  Exp6-only exact={b6}  Exp7-only exact={c7}  McNemar p={mcnemar_p(b6, c7):.3f}")
    print()
print("raw 'correct' values seen:", dict(raw))

# ---- Tier 4 writer comparison: GLM-written vs Claude-written rewrites ----
print("\n" + "=" * 78)
print("LEGACY: TIER 4 WRITER COMPARISON, TRUNCATED VIEW (superseded by the matched-window arm)")
print("=" * 78)
for lang, cfg in LANGS.items():
    U = usable_set(cfg["data"])
    print(f"\n{lang.upper()}")
    print(f"{'model':<28}{'GLM n':>7}{'GLM acc':>9}{'Cl n':>7}{'Cl acc':>9} | {'paired n':>9}{'GLM':>8}{'Claude':>8}{'GLM-only':>9}{'Cl-only':>8}{'p':>8}")
    for m in MODELS:
        pm = os.path.join(BASE, cfg["res"], cfg["five"].format(m=m))
        pc = pm.replace(".csv", "__t5-claude-sonnet.csv")
        g, _, _ = load_five(pm, U, collections.Counter())
        c, _, _ = load_five(pc, U, collections.Counter())
        gate = lambda p, b: g.get((p, b, "2"))
        G = {(p, b): v for (p, b, t), v in g.items() if t == "5" and gate(p, b)}
        C = {(p, b): v for (p, b, t), v in c.items() if t == "5" and gate(p, b)}
        both = sorted(set(G) & set(C))
        gb = sum(G[k] and not C[k] for k in both)
        cb = sum(C[k] and not G[k] for k in both)
        print(f"{m:<28}{len(G):>7}{pct(sum(G.values()), len(G)):>9}{len(C):>7}{pct(sum(C.values()), len(C)):>9} | "
              f"{len(both):>9}{pct(sum(G[k] for k in both), len(both)):>8}{pct(sum(C[k] for k in both), len(both)):>8}"
              f"{gb:>9}{cb:>8}{mcnemar_p(gb, cb):>8.3f}")


# ---- Tier 4 view ablation: truncated (old) vs matched window (new), same writer ----
print("\n" + "=" * 78)
print("TIER 4 VIEW ABLATION: first-120-lines view (old) vs matched +-60 window (new), Claude-written")
print("=" * 78)
for lang, cfg in LANGS.items():
    U = usable_set(cfg["data"])
    print(f"\n{lang.upper()}")
    print(f"{'model':<28}{'old n':>7}{'old acc':>9}{'new n':>7}{'new acc':>9} | {'paired n':>9}{'old':>8}{'new':>8}{'old-only':>9}{'new-only':>9}{'p':>8}")
    for m in MODELS:
        pm = os.path.join(BASE, cfg["res"], cfg["five"].format(m=m))
        po = pm.replace(".csv", "__t5-claude-sonnet.csv"); pw = pm.replace(".csv", "__t5-claude-sonnet-win.csv")
        if not (os.path.exists(po) and os.path.exists(pw)): print(f"{m:<28} (missing file)"); continue
        g, _, _ = load_five(pm, U, collections.Counter())
        o, _, _ = load_five(po, U, collections.Counter())
        w, _, _ = load_five(pw, U, collections.Counter())
        gate = lambda p, b: g.get((p, b, "2"))
        O = {(p, b): v for (p, b, t), v in o.items() if t == "5" and gate(p, b)}
        W = {(p, b): v for (p, b, t), v in w.items() if t == "5" and gate(p, b)}
        both = sorted(set(O) & set(W))
        ob = sum(O[k] and not W[k] for k in both); wb = sum(W[k] and not O[k] for k in both)
        print(f"{m:<28}{len(O):>7}{pct(sum(O.values()), len(O)):>9}{len(W):>7}{pct(sum(W.values()), len(W)):>9} | "
              f"{len(both):>9}{pct(sum(O[k] for k in both), len(both)):>8}{pct(sum(W[k] for k in both), len(both)):>8}"
              f"{ob:>9}{wb:>9}{mcnemar_p(ob, wb):>8.3f}")


# ---- ADDITIONAL MODELS: any model run with scripts/run/run_experiment.py (one file, Tiers 1-4) ----
import glob as _glob
print("\n\nADDITIONAL MODELS (T3 scored where T1 correct, T4 where T2 correct; usable bugs only)")
_any = False
for _lang, _cfg in LANGS.items():
    _U = usable_set(_cfg["data"])
    _pre = _cfg["five"].format(m="")[:-4]
    _suf = "__t5-claude-sonnet-win.csv"
    for _pp in sorted(_glob.glob(os.path.join(BASE, _cfg["res"], _pre + "*" + _suf))):
        _m = os.path.basename(_pp)[len(_pre):-len(_suf)]
        if not _m or _m in MODELS: continue
        _d, _, _ = load_five(_pp, _U, collections.Counter())
        _bugs = {}
        for (_pj, _b, _t), _v in _d.items():
            _bugs.setdefault((_pj, _b), {})[_t] = _v
        def _acc(t, gate=None):
            sel = [x for x in _bugs.values() if t in x and (gate is None or x.get(gate))]
            c = sum(1 for x in sel if x[t])
            return f"{c}/{len(sel)} ({pct(c, len(sel))})"
        if not _any:
            print(f"{'lang':<8}{'model':<30}{'T1':>18}{'T2':>18}{'T3':>18}{'T4':>18}   usable bugs"); _any = True
        print(f"{_lang:<8}{_m:<30}{_acc('1'):>18}{_acc('2'):>18}{_acc('3','1'):>18}{_acc('5','2'):>18}   {len(_U)}")
if not _any:
    print("(none: no results files found for models outside the main three)")


# ---- ADDITIONAL MODELS: probes (Exp6 / Exp7) ----
print("\n\nADDITIONAL MODELS: PROBES (exact line match is primary; +-5 secondary)")
_anyp = False
for _lang, _cfg in LANGS.items():
    _U = usable_set(_cfg["data"])
    _pre = _cfg["five"].format(m="")[:-4]
    _suf = "__t5-claude-sonnet-win.csv"
    _ms = sorted({os.path.basename(_pp)[len(_pre):-len(_suf)] for _pp in _glob.glob(os.path.join(BASE, _cfg["res"], _pre + "*" + _suf))} - set(MODELS))
    for _m in _ms:
        _P = {}
        for _tag in ("p6", "p7"):
            _rows = rd(os.path.join(BASE, _cfg["res"], _cfg[_tag].format(m=_m)))
            if _rows is None: continue
            _first = {}
            for _rw in _rows:
                _k = (_rw["project"], str(_rw["bug_id"]), _rw["tier"])
                if (_k[0], _k[1]) in _U and _k not in _first: _first[_k] = _rw
            _P[_tag] = _first
        for _tag, _name in (("p6", "Exp6 bug-ID"), ("p7", "Exp7 context")):
            if _tag not in _P:
                print(f"{_lang:<8}{_m:<30}{_name:<14} (no file)"); continue
            _t2 = [_rw for _k, _rw in _P[_tag].items() if _k[2] == "2"]
            _t1 = [_rw for _k, _rw in _P[_tag].items() if _k[2] == "1"]
            _ex = _w5 = 0
            for _rw in _t2:
                _a, _b = to_int(_rw["reported_line"]), to_int(actual(_rw))
                if _a is not None and _b is not None:
                    _ex += _a == _b; _w5 += abs(_a - _b) <= 5
            _fa = sum(to_int(_rw["reported_line"]) is not None for _rw in _t1)
            _anyp = True
            print(f"{_lang:<8}{_m:<30}{_name:<14} T2 n={len(_t2):>3} exact={_ex:>3} ({pct(_ex,len(_t2))}) +-5={_w5:>3} ({pct(_w5,len(_t2))}) | T1 n={len(_t1):>3} gave a line={_fa:>3} ({pct(_fa,len(_t1))})")
        if "p6" in _P and "p7" in _P:
            _keys = [_k for _k in _P["p6"] if _k[2] == "2" and _k in _P["p7"]]
            def _hit(_rw):
                _a, _b = to_int(_rw["reported_line"]), to_int(actual(_rw)); return _a is not None and _b is not None and _a == _b
            _b6 = sum(_hit(_P["p6"][_k]) and not _hit(_P["p7"][_k]) for _k in _keys)
            _c7 = sum(_hit(_P["p7"][_k]) and not _hit(_P["p6"][_k]) for _k in _keys)
            print(f"{'':<38}paired T2 bugs={len(_keys)}  Exp6-only exact={_b6}  Exp7-only exact={_c7}  McNemar p={mcnemar_p(_b6, _c7):.3f}")
if not _anyp:
    print("(none: no probe results for models outside the main three)")
