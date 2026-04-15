"""
One-time Wikipedia scraper for 2025-26 UEFA competition data.
Usage:  python backend/scraper.py
Output: data/results_cache.json

Scrapes qualifying rounds, league phase, and knockout phase for
UCL, UEL, and UECL from Wikipedia.
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA = "UEFA-Coefficient-Simulator/1.0 (educational, github/private)"
DELAY = 1.5  # seconds between requests

URLS = {
    "ucl": {
        "qualifying":    "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_qualifying",
        "league_phase":  "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_league_phase",
        "knockout":      "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_knockout_phase",
    },
    "uel": {
        "qualifying":    "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_qualifying",
        "league_phase":  "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_league_phase",
        "knockout":      "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_knockout_phase",
    },
    "uecl": {
        "qualifying":    "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_qualifying",
        "league_phase":  "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_league_phase",
        "knockout":      "https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_knockout_phase",
    },
}

# Ordered qualifying round labels (result tables appear in this order)
QUAL_ROUNDS = ["Q1", "Q2", "Q3", "PO"]
# Ordered knockout round labels (result tables appear in this order)
KO_ROUNDS   = ["KPO", "R16", "QF", "SF", "F"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> BeautifulSoup:
    print(f"  GET {url}", flush=True)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    time.sleep(DELAY)
    return BeautifulSoup(r.text, "html.parser")


# ---------------------------------------------------------------------------
# Score / cell parsing utilities
# ---------------------------------------------------------------------------

EN_DASH = "\u2013"

MONTHS = {"jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"}

def parse_score(raw: str):
    """
    Parse a score string like '2–1', '0–5 (a.e.t.)', '1–1 (4–2 p)' etc.
    Returns dict with keys: goals (list[int,int] or None), aet (bool), pens (list[int,int] or None)
    Returns None if the string doesn't look like a score (e.g. a date like '28–29 Apr' or '–').
    """
    if not raw:
        return None
    # Strip footnote markers like [a], [b]
    raw = re.sub(r"\[[^\]]*\]", "", raw).strip()

    # Reject date strings: if any word is a month name, it's not a score
    words = re.findall(r"[A-Za-z]+", raw)
    if any(w.lower() in MONTHS for w in words):
        return None

    aet = "(a.e.t.)" in raw or "(aet)" in raw.lower()
    pen_match = re.search(r"\((\d+)[–\-](\d+)\s*p\)", raw, re.IGNORECASE)
    pens = [int(pen_match.group(1)), int(pen_match.group(2))] if pen_match else None

    # Strip everything after the first '(' for the main score
    main = re.split(r"\(", raw)[0].strip()
    score_match = re.search(r"(\d+)\s*[–\-]\s*(\d+)", main)
    if not score_match:
        return None
    goals = [int(score_match.group(1)), int(score_match.group(2))]
    return {"goals": goals, "aet": aet, "pens": pens}


def extract_team_cell(cell):
    """
    Extract team name and country from a table cell.
    Returns (team_name, country) tuple.
    Country comes from the flag <img alt="..."> inside flagicon span.
    Team name comes from the <a> tag (falling back to cell text).
    """
    # Country from flag
    flag_img = cell.find("img")
    country = flag_img["alt"].strip() if flag_img and flag_img.get("alt") else ""

    # Team name: prefer the <a> that isn't a flag link
    team = ""
    for a in cell.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        # Skip flag links (they link to federation pages, typically empty text or flag)
        if text and "Flag" not in text and len(text) > 1:
            team = text
            break

    if not team:
        # Fallback: raw cell text minus flag text
        team = cell.get_text(strip=True)

    return team, country


def is_winner(cell) -> bool:
    """Return True if this cell's team is bolded (= winner/advancing team)."""
    return bool(cell.find(["strong", "b"]))


def is_score_cell(raw: str) -> bool:
    """Check if cell text looks like a score (contains a dash between digits)."""
    return bool(re.search(r"\d\s*[–\-]\s*\d", raw))


# ---------------------------------------------------------------------------
# Qualifying page parser
# ---------------------------------------------------------------------------

def parse_qualifying(soup: BeautifulSoup) -> dict:
    """
    Find all result tables (headers: Team 1, Agg., Team 2, 1st leg, 2nd leg)
    in document order and assign them to qualifying rounds Q1, Q2, Q3, PO.
    """
    result_tables = []
    for t in soup.find_all("table", class_="wikitable"):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if "Team 1" in headers and "Team 2" in headers:
            result_tables.append(t)

    rounds = {}
    for i, table in enumerate(result_tables):
        label = QUAL_ROUNDS[i] if i < len(QUAL_ROUNDS) else f"R{i}"
        rounds[label] = parse_two_legged_table(table)

    return rounds


def parse_two_legged_table(table) -> list:
    """
    Parse a table with columns: Team 1 | Agg. | Team 2 | 1st leg | 2nd leg
    Returns list of tie dicts.
    """
    ties = []
    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue

        team1, country1 = extract_team_cell(cells[0])
        team2, country2 = extract_team_cell(cells[2])

        if not team1 or not team2:
            continue
        # Skip placeholder rows (undrawn future rounds)
        if team1.lower().startswith("winner") or team2.lower().startswith("winner"):
            continue

        winner = "team1" if is_winner(cells[0]) else ("team2" if is_winner(cells[2]) else None)

        agg_raw  = cells[1].get_text(strip=True)
        leg1_raw = cells[3].get_text(strip=True)
        leg2_raw = cells[4].get_text(strip=True)

        agg  = parse_score(agg_raw)
        leg1 = parse_score(leg1_raw)
        leg2 = parse_score(leg2_raw)

        # leg2 not yet played (shows a date like "16 Apr")
        leg2_played = leg2 is not None

        tie = {
            "team1": team1, "team1_country": country1,
            "team2": team2, "team2_country": country2,
            "winner": winner,
            "aggregate": agg["goals"] if agg else None,
            "agg_aet": agg["aet"] if agg else False,
            "agg_pens": agg["pens"] if agg else None,
            "leg1": leg1["goals"] if leg1 else None,
            "leg1_aet": leg1["aet"] if leg1 else False,
            "leg1_pens": leg1["pens"] if leg1 else None,
            "leg2": leg2["goals"] if leg2_played else None,
            "leg2_aet": leg2["aet"] if leg2_played else False,
            "leg2_pens": leg2["pens"] if leg2_played else None,
            "leg2_played": leg2_played,
        }
        ties.append(tie)

    return ties


# ---------------------------------------------------------------------------
# League phase parser
# ---------------------------------------------------------------------------

def parse_league_phase(soup: BeautifulSoup) -> list:
    """
    Find the standings table (Pos, Team, Pld, W, D, L, ...) and extract
    team name, country, position, W, D, L.
    """
    for t in soup.find_all("table", class_="wikitable"):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if "Pos" in headers and "W" in headers and "D" in headers and "L" in headers:
            return _parse_standings_table(t, headers)
    return []


def _parse_standings_table(table, headers: list) -> list:
    col = {h: i for i, h in enumerate(headers)}
    rows = table.find_all("tr")
    standings = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 6:
            continue
        try:
            pos = int(cells[col.get("Pos", 0)].get_text(strip=True))
        except ValueError:
            continue  # skip sub-header rows

        # Team cell: find the <th> or td with flag + name
        team_cell = None
        for c in cells:
            if c.find("span", class_="flagicon"):
                team_cell = c
                break
        if team_cell is None:
            team_cell = cells[col.get("Team", 1)]

        team, country = extract_team_cell(team_cell)

        def _int(key):
            idx = col.get(key)
            if idx is None:
                return 0
            try:
                return int(cells[idx].get_text(strip=True))
            except (ValueError, IndexError):
                return 0

        standings.append({
            "position": pos,
            "team": team,
            "country": country,
            "W": _int("W"),
            "D": _int("D"),
            "L": _int("L"),
        })
    return standings


# ---------------------------------------------------------------------------
# Knockout phase parser
# ---------------------------------------------------------------------------

def parse_knockout(soup: BeautifulSoup) -> dict:
    """
    Find all two-legged result tables in the knockout page and assign them
    to KO rounds in order: KPO, R16, QF, SF, F.
    """
    result_tables = []
    for t in soup.find_all("table", class_="wikitable"):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if "Team 1" in headers and "Team 2" in headers:
            result_tables.append(t)

    rounds = {}
    for i, table in enumerate(result_tables):
        label = KO_ROUNDS[i] if i < len(KO_ROUNDS) else f"R{i}"
        rounds[label] = parse_two_legged_table(table)

    return rounds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_competition(comp: str) -> dict:
    print(f"\n=== {comp.upper()} ===")
    urls = URLS[comp]

    print("Qualifying...")
    qualifying = parse_qualifying(fetch_page(urls["qualifying"]))
    for rnd, ties in qualifying.items():
        print(f"  {rnd}: {len(ties)} ties")

    print("League phase...")
    league_phase = parse_league_phase(fetch_page(urls["league_phase"]))
    print(f"  {len(league_phase)} teams")

    print("Knockout phase...")
    knockout = parse_knockout(fetch_page(urls["knockout"]))
    for rnd, ties in knockout.items():
        played = sum(1 for t in ties if t.get("leg2_played"))
        print(f"  {rnd}: {len(ties)} ties ({played} fully played)")

    return {
        "qualifying": qualifying,
        "league_phase": league_phase,
        "knockout": knockout,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("UEFA 2025-26 Coefficient Data Scraper")
    print("Source: Wikipedia (en.wikipedia.org)")
    print("=" * 50)

    data = {"season": "2025-26"}
    for comp in ["ucl", "uel", "uecl"]:
        data[comp] = scrape_competition(comp)

    out_path = Path(__file__).parent.parent / "data" / "results_cache.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
