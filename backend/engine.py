"""Pure coefficient helpers for the UEFA 5th Spot simulator.

This module keeps the ruleset isolated from the UI and data-loading code.
It implements the current-season association calculations described in
CLAUDE.md and cross-checks the relevant Annex D rules:

- Match points: 1/0.5 in qualifying, 2/1 in league phase and knockout.
- League phase bonus points from the official D.5 table.
- Knockout progression bonuses for R16, QF, SF, and Final.
- UECL qualifying elimination bonuses.
- Association coefficient = total points / clubs entered, truncated to 3 dp.
- Fixed results from the cached dataset are read-only; overrides only apply
  to future, still-editable knockout legs.

The current simulator is season-specific, so association tie handling uses a
deterministic fallback when two associations have identical averages.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Iterable, Literal, Mapping, Sequence

Competition = Literal["UCL", "UEL", "UECL"]
Stage = Literal["qualifying", "league", "knockout", "final"]
ProgressionRound = Literal["R16", "QF", "SF", "F"]
QualifyingEliminationRound = Literal["Q1", "Q2", "Q3", "PO"]

_THOUSANDTH = Decimal("0.001")

_UCL_LEAGUE_BONUSES = [
    12.000, 11.750, 11.500, 11.250, 11.000, 10.750, 10.500, 10.250,
    10.000, 9.750, 9.500, 9.250, 9.000, 8.750, 8.500, 8.250,
    8.000, 7.750, 7.500, 7.250, 7.000, 6.750, 6.500, 6.250,
]
_UEL_LEAGUE_BONUSES = [
    6.000, 5.750, 5.500, 5.250, 5.000, 4.750, 4.500, 4.250,
    4.000, 3.750, 3.500, 3.250, 3.000, 2.750, 2.500, 2.250,
    2.000, 1.750, 1.500, 1.250, 1.000, 0.750, 0.500, 0.250,
]
_UECL_LEAGUE_BONUSES = [
    4.000, 3.750, 3.500, 3.250, 3.000, 2.750, 2.500, 2.250,
    2.000, 1.875, 1.750, 1.625, 1.500, 1.375, 1.250, 1.125,
    1.000, 0.875, 0.750, 0.625, 0.500, 0.375, 0.250, 0.125,
]

_PROGRESSION_BONUS = {
    "UCL": 1.5,
    "UEL": 1.0,
    "UECL": 0.5,
}

_UECL_QUALIFYING_EXIT_BONUS = {
    "Q1": 1.0,
    "Q2": 1.5,
    "Q3": 2.0,
    "PO": 2.5,
}


@dataclass(frozen=True)
class ClubSeasonSummary:
    """Season totals for a single club."""

    club_id: str
    club_name: str
    association_id: str
    points: float
    season_coefficients: tuple[float, ...] = ()
    association_coefficient: float | None = None
    domestic_league_position: int | None = None


@dataclass(frozen=True)
class AssociationSeasonSummary:
    """Aggregated current-season association totals."""

    association_id: str
    association_name: str
    clubs_entered: int
    total_points: float
    average_points: float


def truncate_to_thousandth(value: float) -> float:
    """Truncate a positive floating-point value to 3 decimal places."""
    decimal_value = Decimal(str(value))
    return float(decimal_value.quantize(_THOUSANDTH, rounding=ROUND_DOWN))


def match_points(home_score: int, away_score: int, stage: Stage) -> tuple[float, float]:
    """Return the points earned by the home and away teams for a single match."""
    if stage == "qualifying":
        win_points = 1.0
        draw_points = 0.5
    elif stage in {"league", "knockout", "final"}:
        win_points = 2.0
        draw_points = 1.0
    else:  # pragma: no cover - protected by Literal typing, retained for safety.
        raise ValueError(f"Unsupported stage: {stage}")

    if home_score > away_score:
        return win_points, 0.0
    if away_score > home_score:
        return 0.0, win_points
    return draw_points, draw_points


def league_phase_bonus(competition: Competition, position: int) -> float:
    """Return the league-phase bonus for a club finishing at a given position."""
    if position < 1 or position > 36:
        raise ValueError("League phase position must be in the range 1..36")

    if competition == "UCL":
        if position <= 24:
            return _UCL_LEAGUE_BONUSES[position - 1]
        return 6.0
    if competition == "UEL":
        if position <= 24:
            return _UEL_LEAGUE_BONUSES[position - 1]
        return 0.0
    if competition == "UECL":
        if position <= 24:
            return _UECL_LEAGUE_BONUSES[position - 1]
        return 0.0
    raise ValueError(f"Unsupported competition: {competition}")


def knockout_progression_bonus(competition: Competition, round_name: ProgressionRound) -> float:
    """Return the bonus for reaching a knockout round."""
    if round_name not in {"R16", "QF", "SF", "F"}:
        raise ValueError(f"Unsupported progression round: {round_name}")
    try:
        return _PROGRESSION_BONUS[competition]
    except KeyError as exc:  # pragma: no cover - protected by Literal typing.
        raise ValueError(f"Unsupported competition: {competition}") from exc


def uecl_qualifying_elimination_bonus(round_name: QualifyingEliminationRound) -> float:
    """Return the UEFA Conference League qualifying elimination bonus."""
    try:
        return _UECL_QUALIFYING_EXIT_BONUS[round_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported UECL qualifying round: {round_name}") from exc


def association_coefficient(total_points: float, clubs_entered: int) -> float:
    """Compute the season coefficient for an association."""
    if clubs_entered <= 0:
        raise ValueError("clubs_entered must be greater than zero")
    return truncate_to_thousandth(total_points / clubs_entered)


def summarize_associations(
    clubs: Sequence[ClubSeasonSummary],
    association_names: Mapping[str, str] | None = None,
) -> list[AssociationSeasonSummary]:
    """Aggregate club totals into per-association season summaries."""
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    seen_clubs: set[str] = set()

    for club in clubs:
        totals[club.association_id] = totals.get(club.association_id, 0.0) + club.points
        if club.club_id not in seen_clubs:
            seen_clubs.add(club.club_id)
            counts[club.association_id] = counts.get(club.association_id, 0) + 1

    summaries: list[AssociationSeasonSummary] = []
    for association_id, total_points in totals.items():
        clubs_entered = counts[association_id]
        average = association_coefficient(total_points, clubs_entered)
        summaries.append(
            AssociationSeasonSummary(
                association_id=association_id,
                association_name=(association_names or {}).get(association_id, association_id),
                clubs_entered=clubs_entered,
                total_points=truncate_to_thousandth(total_points),
                average_points=average,
            )
        )

    summaries.sort(
        key=lambda item: (
            -item.average_points,
            -item.total_points,
            item.association_name.lower(),
            item.association_id,
        )
    )
    return summaries


def rank_clubs(
    clubs: Sequence[ClubSeasonSummary],
) -> list[ClubSeasonSummary]:
    """Rank clubs using the Annex D.8-style tie-breakers.

    The current app only needs association rankings, but this helper keeps the
    engine ready for later club-level views.
    """
    return sorted(
        clubs,
        key=lambda club: (
            tuple(-value for value in club.season_coefficients[:5]),
            -(club.association_coefficient or 0.0),
            club.domestic_league_position if club.domestic_league_position is not None else 10**9,
            club.club_name.lower(),
            club.club_id,
        ),
    )
