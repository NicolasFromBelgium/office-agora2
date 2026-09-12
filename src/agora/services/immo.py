"""Read the immo crawler SQLite and score listings with pure maths (no LLM)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from statistics import median
from typing import Any

BXL_POSTAL = {str(c) for c in list(range(1000, 1211))}
RING_POSTAL = {
    "1410",
    "1420",
    "1500",
    "1600",
    "1620",
    "1630",
    "1640",
    "1650",
    "1700",
    "1730",
    "1780",
    "1800",
    "1830",
    "1850",
    "1930",
    "1950",
    "1970",
    "3080",
    "3090",
}

PEB_POINTS = {
    "A++": 18,
    "A+": 16,
    "A": 14,
    "B": 10,
    "C": 6,
    "D": 2,
    "E": -2,
    "F": -6,
    "G": -10,
}

# Fallback rent €/m²/month when the crawl has too few rents in a commune.
DEFAULT_RENT_M2 = {
    "1000": 20.0,
    "1050": 22.0,
    "1040": 20.0,
    "1060": 18.5,
    "1180": 18.0,
    "1200": 19.0,
    "1150": 19.5,
    "1160": 17.5,
    "1030": 16.5,
    "1070": 15.0,
    "1190": 16.0,
    "1080": 14.5,
    "1090": 15.0,
    "1140": 15.5,
    "1170": 17.0,
    "1210": 16.5,
    "1410": 16.0,
    "1640": 16.5,
    "1930": 15.5,
    "default": 16.0,
}


def _connect(path: Path) -> sqlite3.Connection | None:
    if not path.is_file():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def bot_running(state_path: Path) -> dict[str, Any]:
    if not state_path.is_file():
        return {"running": False, "bots": []}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"running": False, "bots": []}
    bots = list((data.get("running") or {}).keys())
    return {"running": bool(bots), "bots": bots, "updated": data.get("updated")}


def fetch_listings(
    db_path: Path,
    *,
    listing_type: str = "",
    property_type: str = "",
    city: str = "",
    postal_code: str = "",
    q: str = "",
    sort: str = "last_seen",
    direction: str = "desc",
    limit: int = 80,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    con = _connect(db_path)
    if con is None:
        return [], 0
    allowed_sort = {
        "last_seen",
        "price",
        "surface_m2",
        "city",
        "postal_code",
        "peb",
        "photo_count",
    }
    if sort not in allowed_sort:
        sort = "last_seen"
    direction_sql = "ASC" if direction == "asc" else "DESC"
    where = ["1=1"]
    params: list[Any] = []
    if listing_type in {"sale", "rent"}:
        where.append("listing_type = ?")
        params.append(listing_type)
    if property_type:
        where.append("property_type = ?")
        params.append(property_type)
    if city:
        where.append("lower(city) LIKE ?")
        params.append(f"%{city.lower()}%")
    if postal_code:
        where.append("postal_code = ?")
        params.append(postal_code)
    if q:
        where.append("(title LIKE ? OR url LIKE ? OR agency LIKE ? OR contact_email LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    clause = " AND ".join(where)
    try:
        total = con.execute(f"SELECT COUNT(*) FROM listings WHERE {clause}", params).fetchone()[0]
        order = f"SELECT * FROM listings WHERE {clause} ORDER BY {sort} {direction_sql}"
        rows = con.execute(f"{order} LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    except sqlite3.OperationalError:
        con.close()
        return [], 0
    con.close()
    return [dict(r) for r in rows], int(total)


def _median(values: list[float]) -> float | None:
    clean = [v for v in values if v and v > 0]
    if len(clean) < 3:
        return None
    return float(median(clean))


def commune_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    buckets: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        postal = str(row.get("postal_code") or "")
        if not postal:
            continue
        bucket = buckets.setdefault(postal, {"sale_m2": [], "rent_m2": []})
        surface = row.get("surface_m2") or 0
        price = row.get("price") or 0
        if not surface or not price:
            continue
        per = float(price) / float(surface)
        if row.get("listing_type") == "rent":
            bucket["rent_m2"].append(per)
        else:
            bucket["sale_m2"].append(per)
    out: dict[str, dict[str, float]] = {}
    for postal, vals in buckets.items():
        item: dict[str, float] = {}
        sale_med = _median(vals["sale_m2"])
        rent_med = _median(vals["rent_m2"])
        if sale_med:
            item["sale_m2"] = sale_med
        if rent_med:
            item["rent_m2"] = rent_med
        if item:
            out[postal] = item
    return out


def _rent_m2(postal: str, stats: dict[str, dict[str, float]]) -> float:
    if postal in stats and stats[postal].get("rent_m2"):
        return stats[postal]["rent_m2"]
    return DEFAULT_RENT_M2.get(postal, DEFAULT_RENT_M2["default"])


def score_listing(row: dict[str, Any], stats: dict[str, dict[str, float]]) -> dict[str, Any]:
    notes: list[str] = []
    score = 50.0
    postal = str(row.get("postal_code") or "")
    surface = float(row.get("surface_m2") or 0)
    price = float(row.get("price") or 0)
    price_m2 = float(row.get("price_per_m2") or 0)
    if not price_m2 and price and surface:
        price_m2 = price / surface

    if postal in BXL_POSTAL:
        score += 8
        notes.append("Localisation Bruxelles (19 communes).")
    elif postal in RING_POSTAL:
        score += 4
        notes.append("Ceinture bruxelloise.")

    sale_med = (stats.get(postal) or {}).get("sale_m2")
    if row.get("listing_type") != "rent" and price_m2 and sale_med:
        delta = (sale_med - price_m2) / sale_med
        score += max(-18.0, min(18.0, delta * 40))
        if delta > 0.08:
            notes.append(f"Prix/m² {price_m2:.0f} € sous la médiane commune ({sale_med:.0f} €).")
        elif delta < -0.08:
            notes.append(f"Prix/m² {price_m2:.0f} € au-dessus de la médiane ({sale_med:.0f} €).")

    estimated_yield = None
    if row.get("listing_type") != "rent" and price and surface:
        rent_guess = _rent_m2(postal, stats) * surface * 12
        estimated_yield = rent_guess / price
        score += max(-12.0, min(16.0, (estimated_yield - 0.045) * 250))
        notes.append(f"Rendement locatif brut estimé {estimated_yield * 100:.1f} %.")
    elif row.get("listing_type") == "rent" and price_m2:
        bench = _rent_m2(postal, stats)
        if price_m2 < bench * 0.92:
            score += 6
            notes.append("Loyer/m² sous le référentiel commune.")
        elif price_m2 > bench * 1.12:
            score -= 6
            notes.append("Loyer/m² au-dessus du référentiel commune.")

    peb = str(row.get("peb") or "").upper()
    if peb in PEB_POINTS:
        score += PEB_POINTS[peb]
        notes.append(f"PEB {peb} ({PEB_POINTS[peb]:+d}).")

    if row.get("garden"):
        score += 3
        notes.append("Jardin.")
    if row.get("terrace") or row.get("balcony"):
        score += 2
        notes.append("Terrasse/balcon.")
    if row.get("parking"):
        score += 3
        notes.append("Parking.")
    if row.get("lift"):
        score += 1
    if row.get("electrical_conformity") == "oui":
        score += 2
        notes.append("Conformité électrique indiquée.")
    if str(row.get("flood_zone") or "").upper() == "NON_FLOOD_ZONE":
        score += 1
    if row.get("newly_built"):
        score += 3
        notes.append("Neuf / récente construction.")

    score = max(0.0, min(100.0, round(score, 1)))
    if score >= 75:
        label = "fort"
    elif score >= 60:
        label = "intéressant"
    elif score >= 45:
        label = "prudent"
    else:
        label = "faible"
    critique = " ".join(notes) or "Données insuffisantes pour une lecture fine."
    return {
        **row,
        "score": score,
        "score_label": label,
        "estimated_yield": estimated_yield,
        "price_m2": price_m2 or None,
        "critique": critique,
        "qwen_critique": None,
        "qwen_score": None,
    }


def scored_listings(
    db_path: Path, **filters: Any
) -> tuple[list[dict[str, Any]], int, dict[str, dict[str, float]]]:
    extra = {k: v for k, v in filters.items() if k != "limit"}
    rows, total = fetch_listings(db_path, limit=500, offset=0, **extra)
    stats = commune_stats(rows)
    ranked = [score_listing(row, stats) for row in rows]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    limit = int(filters.get("limit") or 80)
    return ranked[:limit], total, stats


def heuristic_tasks(scored: list[dict[str, Any]]) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    for row in scored[:12]:
        if row["score"] < 55:
            continue
        title = (row.get("title") or "Bien")[:80]
        city = row.get("city") or row.get("postal_code") or ""
        contact = (
            row.get("contact_phone") or row.get("contact_email") or row.get("agency") or "l’agence"
        )
        body = (
            f"{row['critique']} Score maths {row['score']}/100 ({row['score_label']}). "
            f"Contact: {contact}."
        )
        tasks.append(
            {
                "title": f"Pister {city}: {title}",
                "description": body,
                "source": "maths",
            }
        )
    if not tasks:
        tasks.append(
            {
                "title": "Lancer le crawler Bruxelles",
                "description": "Pas assez de biens scorés. Lancer le bot immo-be puis revenir.",
                "source": "maths",
            }
        )
    return tasks
