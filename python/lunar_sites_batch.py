#!/usr/bin/env python3
"""
lunar_sites_batch.py
====================
Runs your Sun/Earth elevation program for many lunar sites in one go and
writes one JSON file per site, plus an index.json summary.

It does NOT calculate anything itself. For every site it calls the compute()
function of your existing program, which asks NASA/JPL Horizons.

Built-in sites
--------------
Landing sites copied from the NASA NSSDCA "Table of Anthropogenic Impacts and
Spacecraft on the Moon" (https://nssdc.gsfc.nasa.gov/planetary/lunar/
lunar_artifact_impacts.html, page dated 13 Aug 2025). Only rows whose position
was imaged by the Lunar Reconnaissance Orbiter Camera (note "d" in that table)
are included. Latitude is north positive; longitude is EAST positive. The dates
are the landing dates (UTC) listed in that table.
Table frame: DE421 mean Earth / polar rotation axis reference frame.

Usage examples
--------------
    python lunar_sites_batch.py --list
    python lunar_sites_batch.py --site "Apollo 11"
    python lunar_sites_batch.py --all
    python lunar_sites_batch.py --all --date 2026-11-14
    python lunar_sites_batch.py --csv my_sites.csv

If your main program is not called lunar_elevation.py or is not in the same
folder as this file, point to it:
    python lunar_sites_batch.py --engine "d:/Hackathon/calc 1.py" --site "Apollo 11"

CSV format (first row is a header):
    name,latitude,longitude_east,date,altitude_km
    My site,7.32781,-37.74901,2026-11-14,0
(date and altitude_km may be left empty; altitude defaults to 0 and the date
falls back to --date.)

Exit code: 0 = every site worked, 1 = at least one site failed, 2 = bad usage.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

TABLE_SOURCE = ("NASA NSSDCA, Table of Anthropogenic Impacts and Spacecraft on "
                "the Moon (updated 13 Aug 2025); position imaged by LROC (note d)")

# name, latitude (N +), longitude (E +), landing date (UTC), as listed in the table
SITES = [
    ("Apollo 11",            0.67416,   23.47314, "1969-07-20"),
    ("Apollo 12",           -3.0128,   -23.4219,  "1969-11-19"),
    ("Apollo 14",           -3.64589,  -17.47194, "1971-02-05"),
    ("Apollo 15",           26.13239,    3.63330, "1971-07-30"),
    ("Apollo 16",           -8.9734,    15.5011,  "1972-04-21"),
    ("Apollo 17",           20.1911,    30.7723,  "1972-12-11"),
    ("Chang'e 3",           44.1214,   -19.5117,  "2013-12-14"),
    ("Chang'e 4",          -45.4561,   177.5885,  "2019-01-03"),
    ("Chang'e 5",           43.0576,   -51.9161,  "2020-12-01"),
    ("Chandrayaan-3",      -69.3741,    32.32,    "2023-08-23"),
    ("SLIM",               -13.3160,    25.2510,  "2024-01-19"),
    ("Odysseus (IM-1)",    -80.13,       1.44,    "2024-02-22"),
    ("Chang'e 6",          -41.6385,  -153.9852,  "2024-06-01"),
    ("Blue Ghost 1",        18.562,     61.810,   "2025-03-02"),
    ("Intuitive Machines 2", -84.7906,   29.1957, "2025-03-06"),
]

REQUIRED_ENGINE_NAMES = ("compute", "parse_latitude", "parse_longitude",
                         "parse_altitude_km", "parse_date",
                         "write_json_atomic", "HorizonsError")


# --------------------------------------------------------------------------
def load_engine(path: str):
    """Load the existing elevation program from a file path."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Could not find the elevation program at: {path}\n"
            "Use --engine to give its full path, for example:\n"
            '  --engine "d:/Hackathon/calc 1.py"')
    spec = importlib.util.spec_from_file_location("lunar_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = [n for n in REQUIRED_ENGINE_NAMES if not hasattr(module, n)]
    if missing:
        raise ImportError(f"{path} does not look like the elevation program; "
                          f"missing: {', '.join(missing)}")
    return module


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "site"


def builtin_sites():
    return [{"name": n, "latitude": la, "longitude_east": lo, "date": d,
             "altitude_km": 0.0, "source": TABLE_SOURCE}
            for n, la, lo, d in SITES]


def csv_sites(path: str, default_date):
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        needed = {"name", "latitude", "longitude_east"}
        cols = {c.strip().lower() for c in (reader.fieldnames or [])}
        if not needed <= cols:
            raise ValueError("CSV needs the columns: name, latitude, "
                             "longitude_east (and optionally date, altitude_km)")
        for i, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue
            date = row.get("date") or default_date
            if not date:
                raise ValueError(f"CSV line {i}: no date and no --date given")
            out.append({"name": row["name"] or f"site_line_{i}",
                        "latitude": row["latitude"],
                        "longitude_east": row["longitude_east"],
                        "date": date,
                        "altitude_km": row.get("altitude_km") or "0",
                        "source": f"user CSV {os.path.basename(path)}"})
    if not out:
        raise ValueError("CSV has no data rows.")
    return out


def pick_site(sites, query: str):
    q = query.strip().lower()
    exact = [s for s in sites if s["name"].lower() == q]
    if exact:
        return exact[0]
    part = [s for s in sites if q in s["name"].lower()]
    if len(part) == 1:
        return part[0]
    if not part:
        raise ValueError(f"No site matches {query!r}. Use --list to see names.")
    names = ", ".join(s["name"] for s in part)
    raise ValueError(f"{query!r} matches several sites ({names}). "
                     "Type the full name.")


# --------------------------------------------------------------------------
def run_site(engine, site, date_override, out_dir, timeout):
    lat = engine.parse_latitude(site["latitude"])
    lon = engine.parse_longitude(site["longitude_east"])
    alt = engine.parse_altitude_km(site["altitude_km"])
    day = engine.parse_date(date_override or site["date"])
    data = engine.compute(lat, lon, alt, day, timeout)
    data["site"] = {"name": site["name"], "coordinate_source": site["source"]}
    path = os.path.join(out_dir, f"{slugify(site['name'])}_{day:%Y%m%d}.json")
    engine.write_json_atomic(data, path)
    return path, day.isoformat()


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Run the lunar Sun/Earth elevation program for many sites.")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--list", action="store_true", help="show built-in sites and exit")
    grp.add_argument("--site", help="run one built-in (or CSV) site by name")
    grp.add_argument("--all", action="store_true", help="run every site")
    ap.add_argument("--csv", help="use your own sites from a CSV file")
    ap.add_argument("--date", help="UTC date YYYY-MM-DD for all sites "
                                   "(default: each site's own landing date)")
    ap.add_argument("--out-dir", default="results", help="output folder (default: results)")
    ap.add_argument("--engine", default=os.path.join(here, "lunar_elevation.py"),
                    help="path to the elevation program (default: lunar_elevation.py "
                         "next to this file)")
    ap.add_argument("--timeout", type=float, default=60, help="Horizons timeout, seconds")
    ap.add_argument("--pause", type=float, default=1.0,
                    help="seconds to wait between sites (default 1)")
    args = ap.parse_args(argv)

    try:
        sites = csv_sites(args.csv, args.date) if args.csv else builtin_sites()
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    if args.list:
        print(f"{'Name':<22} {'Lat (N+)':>10} {'Lon (E+)':>11}  Date (UTC)")
        for s in sites:
            print(f"{s['name']:<22} {s['latitude']!s:>10} {s['longitude_east']!s:>11}  {s['date']}")
        return 0

    if not args.site and not args.all:
        print("Nothing to do: use --list, --site NAME or --all.", file=sys.stderr)
        return 2

    try:
        chosen = sites if args.all else [pick_site(sites, args.site)]
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    try:
        engine = load_engine(args.engine)
    except (OSError, ImportError) as exc:
        print(f"Setup error: {exc}", file=sys.stderr)
        return 2

    try:
        os.makedirs(args.out_dir, exist_ok=True)
    except OSError as exc:
        print(f"Cannot create output folder {args.out_dir}: {exc}", file=sys.stderr)
        return 2

    results = []
    for n, site in enumerate(chosen, start=1):
        print(f"[{n}/{len(chosen)}] {site['name']} ...", file=sys.stderr)
        entry = {"site": site["name"], "latitude_deg": site["latitude"],
                 "longitude_east_deg": site["longitude_east"]}
        try:
            path, day = run_site(engine, site, args.date, args.out_dir, args.timeout)
            entry.update(date_utc=day, file=os.path.basename(path), status="ok")
        except (ValueError, engine.HorizonsError, OSError) as exc:
            entry.update(date_utc=args.date or site["date"], file=None,
                         status="failed", error=str(exc))
            print(f"    FAILED: {exc}", file=sys.stderr)
        results.append(entry)
        if n < len(chosen) and args.pause > 0:
            time.sleep(args.pause)

    index = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "results": results}
    index_path = os.path.join(args.out_dir, "index.json")
    try:
        engine.write_json_atomic(index, index_path)
    except OSError as exc:
        print(f"Could not write {index_path}: {exc}", file=sys.stderr)

    ok = sum(r["status"] == "ok" for r in results)
    print(f"Done: {ok} of {len(results)} sites succeeded. Folder: {args.out_dir}",
          file=sys.stderr)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
