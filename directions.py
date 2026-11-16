"""Directions from the user to a polling unit, via OSRM (public servers by default).
Self-host OSRM or use a paid router for production: set OSRM_CAR / OSRM_FOOT."""
import json
import os
import urllib.request

BASE = {
    "driving": os.getenv("OSRM_CAR", "https://router.project-osrm.org/route/v1/driving"),
    "walking": os.getenv("OSRM_FOOT", "https://routing.openstreetmap.de/routed-foot/route/v1/driving"),
}


def step_text(s):
    m, road = s["maneuver"], s.get("name") or ""
    kind, mod = m.get("type", ""), m.get("modifier", "")
    onto = f" onto {road}" if road else ""
    if kind == "arrive":
        return "You have arrived at the polling unit"
    if kind == "depart":
        return f"Start{' on ' + road if road else ''}"
    if kind in ("roundabout", "rotary"):
        return f"Take the roundabout{onto}"
    if mod == "straight" or kind in ("new name", "continue"):
        return f"Continue straight{onto}"
    return f"Turn {mod}{onto}".replace("Turn  ", "Continue ")


def links(lat, lon, mode):
    travel = "walking" if mode == "walking" else "driving"
    return {"google": f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode={travel}"}


def route(from_lat, from_lon, to_lat, to_lon, mode="driving"):
    url = f"{BASE[mode]}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson&steps=true"
    req = urllib.request.Request(url, headers={"User-Agent": "ng-constitution-rag"})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.load(r)
    if d.get("code") != "Ok" or not d.get("routes"):
        raise ValueError(d.get("message", "No route found"))
    rt = d["routes"][0]
    return {
        "km": round(rt["distance"] / 1000, 1),
        "minutes": max(1, round(rt["duration"] / 60)),
        "path": [[la, lo] for lo, la in rt["geometry"]["coordinates"]],
        "steps": [{"text": step_text(s), "m": round(s["distance"])} for s in rt["legs"][0]["steps"]],
        **links(to_lat, to_lon, mode),
    }
