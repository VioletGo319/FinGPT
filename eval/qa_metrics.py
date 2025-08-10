# eval/qa_metrics.py
import argparse, json, re, time, os, sys, csv
from typing import List, Dict, Any

try:
    import requests
except Exception:
    print("[FATAL] Missing dependency: requests. Install with: pip install requests")
    raise

DEFAULT_FILE = "data/financebench/data/financebench_open_source.jsonl"

# ---- helpers ----

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out

def norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9%.]+", " ", s)
    return re.sub(r"\s+", " ", s)

def f1(pred: str, golds: List[str]) -> float:
    def f1_pair(p, g):
        p_toks = norm(p).split()
        g_toks = norm(g).split()
        if not p_toks and not g_toks: return 1.0
        if not p_toks or not g_toks: return 0.0
        common = {}
        for t in p_toks:
            if t in g_toks:
                common[t] = min(p_toks.count(t), g_toks.count(t))
        overlap = sum(common.values())
        if overlap == 0: return 0.0
        prec = overlap / len(p_toks)
        rec  = overlap / len(g_toks)
        return 2*prec*rec/(prec+rec)
    return max(f1_pair(pred, g) for g in golds)

def exact_match(pred: str, golds: List[str]) -> int:
    p = norm(pred)
    return int(any(p == norm(g) for g in golds))

def doc_recall_at_k(sources: List[Dict[str, Any]], gold_doc_name: str) -> int:
    gd = os.path.splitext(os.path.basename(gold_doc_name))[0]
    for s in sources:
        sd = os.path.splitext(os.path.basename(s.get("source","")))[0]
        if gd and sd and gd == sd:
            return 1
    return 0

def ensure_file(path: str) -> str:
    if os.path.exists(path):
        return path
    # fallback to default
    for cand in [DEFAULT_FILE, os.path.join(".", DEFAULT_FILE)]:
        if os.path.exists(cand):
            return cand
    print(f"[ERROR] JSONL not found. Tried: {path} and {DEFAULT_FILE}")
    sys.stdout.flush()
    sys.exit(1)

def health_check(host: str, timeout: float = 3.0):
    try:
        r = requests.get(host.rstrip("/") + "/health", timeout=timeout)
        print(f"Health: status={r.status_code} body={getattr(r,'text','')[:60]}")
    except Exception as e:
        print(f"[WARN] /health check failed: {e}")
    sys.stdout.flush()

# ---- main ----

def main():
    print("[qa_metrics] starting… cwd=", os.getcwd())
    sys.stdout.flush()

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8000", help="FastAPI host")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--n", type=int, default=200, help="evaluate first N samples (for speed)")
    ap.add_argument("--k", type=int, default=3, help="top-k used in /ask (doc recall@k)")
    ap.add_argument("--timeout", type=float, default=15.0, help="per-request timeout in seconds")
    ap.add_argument("--progress", action="store_true", help="print progress for each item")
    ap.add_argument("--every", type=int, default=10, help="print progress every N items when --progress is off")
    ap.add_argument("--save_csv", type=str, default="", help="optional path to save per-item results as CSV")
    args = ap.parse_args()

    fpath = ensure_file(args.file)
    print(f"Using file: {fpath}")
    sys.stdout.flush()

    # health check
    health_check(args.host, timeout=3.0)

    data = load_jsonl(fpath)[:args.n]
    total = len(data)
    if total == 0:
        print("No samples loaded. Check --file path.")
        sys.stdout.flush()
        return

    url = args.host.rstrip("/") + "/ask/"
    print(f"Start evaluation: total={total} host={url} timeout={args.timeout}s k={args.k}")
    sys.stdout.flush()

    ems, f1s, recs, lat = [], [], [], []
    ok = 0

    writer = None
    fcsv = None
    if args.save_csv:
        os.makedirs(os.path.dirname(args.save_csv) or ".", exist_ok=True)
        fcsv = open(args.save_csv, "w", newline="", encoding="utf-8")
        writer = csv.writer(fcsv)
        writer.writerow(["idx","em","f1","recall","latency_sec"])  # header

    for i, ex in enumerate(data, 1):
        q = ex.get("question") or ex.get("query") or ""
        gold = ex.get("answer")
        golds = [gold] if isinstance(gold, str) else (gold or [])
        if not q or not golds:
            if args.progress:
                print(f"[{i}/{total}] skipped (no q/ans)")
            elif i % args.every == 0:
                print(f"[{i}/{total}] processed…")
            sys.stdout.flush()
            continue
        t0 = time.time()
        try:
            r = requests.post(url, json={"question": q, "top_k": args.k}, timeout=args.timeout)
            r.raise_for_status()
            resp = r.json()
            pred = resp.get("answer","")
            sources = resp.get("sources",[])
            t1 = time.time()
            em = exact_match(pred, golds)
            f1v = f1(pred, golds)
            rc = doc_recall_at_k(sources, ex.get("doc_name",""))
            dt = t1 - t0
            ems.append(em); f1s.append(f1v); recs.append(rc); lat.append(dt)
            ok += 1
            if writer:
                writer.writerow([i, em, f1v, rc, dt])
            if args.progress:
                print(f"[{i}/{total}] ok in {dt:.2f}s  EM={em}  F1={f1v:.2f}  R@{args.k}={rc}")
            elif i % args.every == 0:
                print(f"[{i}/{total}] processed…")
            sys.stdout.flush()
        except Exception as e:
            print(f"[{i}/{total}] error: {e}")
            sys.stdout.flush()

    if writer:
        fcsv.close()

    if ok == 0:
        print("No samples evaluated successfully.")
        sys.stdout.flush()
        return

    import statistics as st
    print(f"n={ok}  EM={sum(ems)/ok:.3f}  F1={sum(f1s)/ok:.3f}  R@{args.k}={sum(recs)/ok:.3f}  Latency(P50)={st.median(lat):.3f}s")
    sys.stdout.flush()

if __name__ == "__main__":
    main()