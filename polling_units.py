"""Polling-unit directory. Build once from a CSV:  python polling_units.py data/polling_units.csv
Stored in SQLite (standard library), which also works read-only on Vercel."""
import csv
import math
import os
import sqlite3
import sys

DB = os.getenv("PU_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "polling_units.db"))
ALIASES = {
    "state": ("state", "state_name"),
    "lga": ("lga", "local_government", "lga_name", "local_government_name"),
    "ward": ("ward", "registration_area", "ward_name"),
    "code": ("pu_code", "code", "delimitation", "polling_unit_code"),
    "name": ("pu_name", "polling_unit", "name", "polling_unit_name"),
    "lat": ("latitude", "lat", "location.latitude"),
    "lon": ("longitude", "lon", "lng", "long", "location.longitude"),
}
_con = None


def _num(v, lo, hi):  # keep only coordinates that fall inside Nigeria
    try:
        x = float(v)
        return x if lo <= x <= hi else None
    except (TypeError, ValueError):
        return None


def build_db(csv_path, db_path=DB):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE pu(code TEXT, name TEXT, state TEXT, lga TEXT, ward TEXT, lat REAL, lon REAL, shared INTEGER)")
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = {k.strip().lower(): k for k in rd.fieldnames}
        pick = {k: next((cols[a] for a in al if a in cols), None) for k, al in ALIASES.items()}
        missing = [k for k in ("state", "lga", "ward", "name") if not pick[k]]
        if missing:
            raise SystemExit(f"CSV has no column for: {missing}. Accepted names: {ALIASES}")
        g = lambda r, k: (r.get(pick[k]) or "").strip() if pick[k] else ""
        con.executemany(
            "INSERT INTO pu(code, name, state, lga, ward, lat, lon) VALUES (?,?,?,?,?,?,?)",
            ((g(r, "code"), g(r, "name"), g(r, "state"), g(r, "lga"), g(r, "ward"),
              _num(g(r, "lat"), 3.5, 14.0), _num(g(r, "lon"), 2.5, 15.0)) for r in rd),
        )
    con.execute("CREATE INDEX i_area ON pu(state, lga, ward)")
    con.execute("CREATE INDEX i_geo ON pu(lat, lon)")
    # shared = how many units sit on exactly the same point. >1 means the location is only approximate.
    con.execute("UPDATE pu SET shared = (SELECT COUNT(*) FROM pu p WHERE p.lat = pu.lat AND p.lon = pu.lon) WHERE lat IS NOT NULL")
    con.commit()
    n, located = con.execute("SELECT COUNT(*), COUNT(lat) FROM pu").fetchone()
    con.close()
    return n, located


def _con_ro():
    global _con
    if _con is None:
        _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
        _con.row_factory = sqlite3.Row
    return _con


def _rows(sql, args=()):
    return [dict(r) for r in _con_ro().execute(sql, args)]


def areas():
    out = {}
    for s, l in _con_ro().execute("SELECT DISTINCT state, lga FROM pu ORDER BY 1, 2"):
        out.setdefault(s, []).append(l)
    return out


def search(q="", state="", lga="", ward="", limit=25):
    where, args = [], []
    for col, v in (("state", state), ("lga", lga), ("ward", ward)):
        if v:
            where.append(f"{col} = ? COLLATE NOCASE")
            args.append(v)
    if q:
        where.append("(name LIKE ? OR ward LIKE ? OR code LIKE ?)")
        args += [f"%{q}%"] * 3
    sql = "SELECT * FROM pu" + (" WHERE " + " AND ".join(where) if where else "") + " LIMIT ?"
    return _rows(sql, args + [limit])


def haversine(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def nearby(lat, lon, km=5, limit=10):
    dlat, dlon = km / 111.0, km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    rows = _rows("SELECT * FROM pu WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                 (lat - dlat, lat + dlat, lon - dlon, lon + dlon))
    for r in rows:
        r["km"] = round(haversine(lat, lon, r["lat"], r["lon"]), 2)
    return sorted((r for r in rows if r["km"] <= km), key=lambda r: r["km"])[:limit]


if __name__ == "__main__":
    total, located = build_db(sys.argv[1])
    print(f"{total} polling units, {located} with coordinates -> {DB}")
