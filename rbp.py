#!/usr/bin/env python3

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
GO_TERM = "GO:0003723"
PAGE_SIZE = 1000

DESCRIPTION = (
    "Download all RNA-binding protein structures from RCSB PDB, selected by "
    "the GO:0003723 (RNA binding) molecular-function annotation."
)


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


SESSION = make_session()


def build_query(go_id: str, start: int) -> dict:
    return {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_annotation.annotation_lineage.id",
                "operator": "exact_match",
                "value": go_id,
            },
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": start, "rows": PAGE_SIZE},
            "results_content_type": ["experimental"],
        },
    }


def fetch_all_ids(go_id: str = GO_TERM) -> list:
    ids = []
    start = 0
    total = None
    while total is None or start < total:
        resp = SESSION.post(SEARCH_URL, json=build_query(go_id, start), timeout=60)
        if resp.status_code >= 400:
            print(f"RCSB API returned {resp.status_code}. Response body:\n{resp.text}",
                  file=sys.stderr)
        resp.raise_for_status()
        data = resp.json()
        total = data.get("total_count", 0)
        hits = data.get("result_set", [])
        if not hits:
            break
        ids.extend(h["identifier"] for h in hits)
        start += PAGE_SIZE
        print(f"  fetched {len(ids)}/{total} IDs", file=sys.stderr)
        time.sleep(0.2)
    return sorted(set(ids))


def download_one(pdb_id: str, outdir: str, fmt: str, gz: bool) -> tuple:
    ext = f"{fmt}.gz" if gz else fmt
    url = f"https://files.rcsb.org/download/{pdb_id}.{ext}"
    dest = os.path.join(outdir, f"{pdb_id}.{ext}")
    if os.path.exists(dest):
        return pdb_id, "skipped"
    try:
        r = SESSION.get(url, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        return pdb_id, "ok"
    except Exception as e:
        return pdb_id, f"failed: {e}"


def main():
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--outdir", default="./rbp_structures")
    ap.add_argument("--go-id", default=GO_TERM,
                    help="GO molecular-function ID defining an RNA-binding protein")
    ap.add_argument("--format", default="cif", choices=["cif", "pdb"],
                    help="cif recommended: some large RBP assemblies (e.g. ribosomes) "
                         "have no legacy .pdb file")
    ap.add_argument("--no-gzip", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ids-only", action="store_true",
                    help="only fetch and write the ID list, skip downloading")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"Querying RCSB for entries annotated with {args.go_id} ...", file=sys.stderr)
    ids = fetch_all_ids(args.go_id)
    print(f"Found {len(ids)} PDB entries.", file=sys.stderr)

    id_list_path = os.path.join(args.outdir, "pdb_ids.txt")
    with open(id_list_path, "w") as f:
        f.write("\n".join(ids))
    print(f"ID list written to {id_list_path}", file=sys.stderr)

    if args.ids_only:
        return

    print(f"Downloading {len(ids)} structures with {args.workers} workers "
          f"(format={args.format}, gzip={not args.no_gzip}) ...", file=sys.stderr)
    ok = fail = skip = 0
    failed_ids = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(download_one, pid, args.outdir, args.format, not args.no_gzip): pid
            for pid in ids
        }
        for fut in as_completed(futures):
            pid, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skipped":
                skip += 1
            else:
                fail += 1
                failed_ids.append(pid)
                print(f"  {pid}: {status}", file=sys.stderr)

    print(f"Done. ok={ok} skipped={skip} failed={fail}", file=sys.stderr)

    if failed_ids:
        failed_path = os.path.join(args.outdir, "failed_ids.txt")
        with open(failed_path, "w") as f:
            f.write("\n".join(failed_ids))
        print(f"{len(failed_ids)} IDs still failed after retries -> {failed_path}\n"
              f"Just rerun the exact same command: already-downloaded files are "
              f"skipped automatically, so it will only retry what's missing.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
