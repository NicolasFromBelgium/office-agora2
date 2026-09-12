"""Math scoring for immo listings does not need Qwen."""

import json
import sqlite3
from pathlib import Path

from agora.services.immo import (
    bot_running,
    commune_stats,
    fetch_listings,
    heuristic_tasks,
    score_listing,
    scored_listings,
)


def _write_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        """CREATE TABLE listings (
            id INTEGER PRIMARY KEY, listing_type TEXT, property_type TEXT, price REAL,
            surface_m2 REAL, price_per_m2 REAL, postal_code TEXT, city TEXT, peb TEXT,
            garden INTEGER, terrace INTEGER, parking INTEGER, lift INTEGER,
            electrical_conformity TEXT, flood_zone TEXT, newly_built INTEGER,
            title TEXT, url TEXT, agency TEXT, contact_email TEXT, contact_phone TEXT,
            last_seen TEXT, photo_count INTEGER
        )"""
    )
    rows = [
        (
            "sale",
            "apartment",
            280000,
            85,
            3294,
            "1050",
            "Ixelles",
            "B",
            0,
            1,
            1,
            1,
            "oui",
            "NON_FLOOD_ZONE",
            0,
            "Appart Ixelles",
            "https://example/1",
            "Agence",
            "a@immo.be",
            None,
            "2026-01-01",
            3,
        ),
        (
            "sale",
            "house",
            520000,
            140,
            3714,
            "1050",
            "Ixelles",
            "D",
            1,
            0,
            1,
            0,
            None,
            None,
            0,
            "Maison Ixelles",
            "https://example/2",
            "Agence",
            None,
            "+322111",
            "2026-01-02",
            1,
        ),
        (
            "rent",
            "apartment",
            1200,
            70,
            17.1,
            "1000",
            "Bruxelles",
            "C",
            0,
            1,
            0,
            1,
            "oui",
            "NON_FLOOD_ZONE",
            1,
            "Kot centre",
            "https://example/3",
            "Agence",
            None,
            None,
            "2026-01-03",
            0,
        ),
        (
            "sale",
            "apartment",
            310000,
            80,
            3875,
            "1050",
            "Ixelles",
            "A",
            0,
            0,
            0,
            1,
            "oui",
            "NON_FLOOD_ZONE",
            1,
            "Neuf Ixelles",
            "https://example/4",
            "Agence",
            "b@immo.be",
            None,
            "2026-01-04",
            8,
        ),
    ]
    con.executemany(
        """INSERT INTO listings (
            listing_type, property_type, price, surface_m2, price_per_m2, postal_code, city, peb,
            garden, terrace, parking, lift, electrical_conformity, flood_zone, newly_built,
            title, url, agency, contact_email, contact_phone, last_seen, photo_count
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    con.commit()
    con.close()


def test_brussels_sale_gets_a_score_and_critique() -> None:
    row = {
        "listing_type": "sale",
        "property_type": "apartment",
        "price": 280000,
        "surface_m2": 85,
        "postal_code": "1050",
        "city": "Ixelles",
        "peb": "B",
        "garden": 0,
        "terrace": 1,
        "parking": 1,
        "title": "Appartement Ixelles",
        "agency": "Test Immo",
        "contact_email": "a@immo.be",
    }
    stats = {"1050": {"sale_m2": 4500.0}}
    scored = score_listing(row, stats)
    assert 0 <= scored["score"] <= 100
    assert scored["score_label"] in {"fort", "intéressant", "prudent", "faible"}
    assert "Ixelles" in scored["city"]
    assert "PEB" in scored["critique"]
    assert scored["qwen_critique"] is None
    assert scored["estimated_yield"] is not None


def test_heuristic_tasks_from_high_scores() -> None:
    scored = [
        {
            "score": 80,
            "score_label": "fort",
            "title": "Duplex",
            "city": "Uccle",
            "postal_code": "1180",
            "critique": "Bon PEB.",
            "contact_phone": "+322000000",
            "agency": "Agence",
        }
    ]
    tasks = heuristic_tasks(scored)
    assert tasks
    assert tasks[0]["source"] == "maths"
    assert "Uccle" in tasks[0]["title"]


def test_fetch_and_score_from_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "crawl.db"
    _write_db(db)
    rows, total = fetch_listings(db, city="Ixelles", sort="price", direction="asc")
    assert total == 3
    assert rows[0]["price"] <= rows[-1]["price"]
    ranked, scored_total, stats = scored_listings(db, city="Ixelles")
    assert scored_total == 3
    assert "1050" in stats
    assert ranked[0]["score"] >= ranked[-1]["score"]
    assert all(item["qwen_score"] is None for item in ranked)


def test_rent_listing_critique_uses_rent_benchmark() -> None:
    row = {
        "listing_type": "rent",
        "price": 900,
        "surface_m2": 70,
        "price_per_m2": 12.8,
        "postal_code": "1000",
        "city": "Bruxelles",
        "peb": "C",
        "garden": 0,
        "terrace": 1,
        "parking": 0,
        "electrical_conformity": "oui",
        "flood_zone": "NON_FLOOD_ZONE",
        "newly_built": 1,
    }
    scored = score_listing(row, {})
    assert "Loyer/m²" in scored["critique"] or "Bruxelles" in scored["critique"]


def test_bot_running_and_empty_sources(tmp_path: Path) -> None:
    missing = bot_running(tmp_path / "nope.json")
    assert missing["running"] is False
    state = tmp_path / "bot-state.json"
    state.write_text(json.dumps({"running": {"immo-be": {"pid": 1}}, "updated": "now"}))
    live = bot_running(state)
    assert live["running"] is True
    assert "immo-be" in live["bots"]
    rows, total = fetch_listings(tmp_path / "missing.db")
    assert rows == []
    assert total == 0
    tasks = heuristic_tasks([{"score": 10, "title": "x", "city": "y", "critique": ""}])
    assert tasks[0]["title"].startswith("Lancer")


def test_commune_stats_need_three_points() -> None:
    stats = commune_stats(
        [
            {"postal_code": "1050", "listing_type": "sale", "price": 300000, "surface_m2": 80},
            {"postal_code": "1050", "listing_type": "sale", "price": 320000, "surface_m2": 90},
        ]
    )
    assert stats == {}
    stats = commune_stats(
        [
            {"postal_code": "1050", "listing_type": "sale", "price": 300000, "surface_m2": 80},
            {"postal_code": "1050", "listing_type": "sale", "price": 320000, "surface_m2": 90},
            {"postal_code": "1050", "listing_type": "sale", "price": 280000, "surface_m2": 70},
            {"postal_code": "1000", "listing_type": "rent", "price": 1100, "surface_m2": 60},
            {"postal_code": "1000", "listing_type": "rent", "price": 1200, "surface_m2": 65},
            {"postal_code": "1000", "listing_type": "rent", "price": 1300, "surface_m2": 70},
        ]
    )
    assert stats["1050"]["sale_m2"] > 0
    assert stats["1000"]["rent_m2"] > 0
