"""Season simulation helpers for the UEFA 5th Spot simulator.

The simulator works from the cached 2025/26 snapshot on disk and can apply
optional score overrides later when the UI starts sending what-if results.

This module does not fetch data and does not touch the filesystem. It only
derives points and rankings from the structured snapshot payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import unicodedata

from .engine import (
    ClubSeasonSummary,
    AssociationSeasonSummary,
    league_phase_bonus,
    match_points,
    knockout_progression_bonus,
    truncate_to_thousandth,
)


@dataclass(frozen=True)
class MatchOverride:
    """Manual result for a specific leg or single-leg tie."""

    competition: str
    round_name: str
    team1: str
    team2: str
    leg: int
    home_score: int | None = None
    away_score: int | None = None
    advancer: str | None = None


@dataclass(frozen=True)
class SimulationResult:
    """Computed ranking snapshot for the current season."""

    association_rankings: list[AssociationSeasonSummary]
    club_rankings: list[ClubSeasonSummary]
    fifth_champions_league_spot_holder: str
    extra_ucl_spot_associations: tuple[str, str]


def _normalize_id(value: str) -> str:
    """Create a stable identifier from a team name."""
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(value.split())


def _club_id(name: str) -> str:
    return _normalize_id(name)


def _lookup_override(
    overrides: Mapping[str, MatchOverride] | None,
    competition: str,
    round_name: str,
    team1: str,
    team2: str,
    leg: int,
    *,
    base_score: Any | None = None,
) -> MatchOverride | None:
    if not overrides:
        return None
    key = make_match_key(competition, round_name, team1, team2, leg)
    override = overrides.get(key)
    if override is None:
        return None

    # Fixed snapshot results must stay locked. If a leg already has a score we
    # ignore any override score edits, but we still allow an advancer override
    # for ties decided on extra time/penalties where the score is level.
    if _score_pair(base_score) is not None and (
        override.home_score is not None or override.away_score is not None
    ):
        return MatchOverride(
            competition=override.competition,
            round_name=override.round_name,
            team1=override.team1,
            team2=override.team2,
            leg=override.leg,
            home_score=None,
            away_score=None,
            advancer=override.advancer,
        )

    return override


def _score_pair(value: Any) -> tuple[int, int] | None:
    """Normalize a score payload into a two-integer tuple."""
    if value is None:
        return None
    if isinstance(value, MatchOverride):
        if value.home_score is None or value.away_score is None:
            return None
        return value.home_score, value.away_score
    if isinstance(value, list) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, tuple) and len(value) == 2:
        return int(value[0]), int(value[1])
    return None


def make_match_key(
    competition: str,
    round_name: str,
    team1: str,
    team2: str,
    leg: int,
) -> str:
    """Build a stable key for a tie leg."""
    return "|".join(
        [
            competition.upper(),
            round_name.upper(),
            _normalize_id(team1),
            _normalize_id(team2),
            str(leg),
        ]
    )


def _iter_competitions(snapshot: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for competition in ("ucl", "uel", "uecl"):
        data = snapshot.get(competition, {})
        if isinstance(data, Mapping):
            yield competition.upper(), data


def _build_association_rankings(
    club_summaries: Iterable[ClubSeasonSummary],
) -> list[AssociationSeasonSummary]:
    """Aggregate club season points directly into association totals.

    The association coefficient is simply the sum of the clubs' season points
    divided by the number of clubs entered, with truncation to 3 decimals.
    """
    association_names: dict[str, str] = {}
    by_association: dict[str, list[ClubSeasonSummary]] = {}
    for club in club_summaries:
        association_names[club.association_id] = club.association_id
        by_association.setdefault(club.association_id, []).append(club)

    rankings: list[AssociationSeasonSummary] = []
    for association_id, clubs in by_association.items():
        total_points = sum(club.points for club in clubs)
        if not association_id and total_points == 0.0:
            continue
        rankings.append(
            AssociationSeasonSummary(
                association_id=association_id,
                association_name=association_names.get(association_id, association_id),
                clubs_entered=len(clubs),
                total_points=truncate_to_thousandth(total_points),
                average_points=truncate_to_thousandth(total_points / len(clubs)),
            )
        )

    rankings.sort(
        key=lambda item: (
            -item.average_points,
            -item.total_points,
            item.association_name.lower(),
            item.association_id,
        )
    )
    return rankings


def _apply_match_score(
    club_totals: dict[str, float],
    club_names: dict[str, str],
    club_associations: dict[str, str],
    team1: str,
    team1_association: str,
    team2: str,
    team2_association: str,
    home_score: int,
    away_score: int,
    stage: str,
) -> None:
    team1_id = _club_id(team1)
    team2_id = _club_id(team2)
    team1_points, team2_points = match_points(home_score, away_score, stage=stage)
    club_totals[team1_id] = club_totals.get(team1_id, 0.0) + team1_points
    club_totals[team2_id] = club_totals.get(team2_id, 0.0) + team2_points
    club_names.setdefault(team1_id, team1)
    club_names.setdefault(team2_id, team2)
    club_associations.setdefault(team1_id, team1_association)
    club_associations.setdefault(team2_id, team2_association)


def _extract_round_bonus_round(round_name: str) -> str | None:
    if round_name in {"R16", "QF", "SF", "F"}:
        return round_name
    return None


def _team_from_advancer(team1: str, team2: str, advancer: str | None) -> str | None:
    if not advancer:
        return None
    normalized = _normalize_id(str(advancer))
    if normalized == "team1":
        return team1
    if normalized == "team2":
        return team2
    if normalized == _normalize_id(team1):
        return team1
    if normalized == _normalize_id(team2):
        return team2
    return None


def _determine_tie_winner(
    team1: str,
    team2: str,
    leg1: tuple[int, int] | None,
    leg2: tuple[int, int] | None,
    single_leg: bool = False,
    advancer: str | None = None,
    fallback_winner: str | None = None,
) -> str | None:
    if single_leg:
        if leg1 is not None:
            if leg1[0] > leg1[1]:
                return team1
            if leg1[1] > leg1[0]:
                return team2
    else:
        if leg1 is None or leg2 is None:
            explicit = _team_from_advancer(team1, team2, advancer)
            if explicit:
                return explicit
            explicit = _team_from_advancer(team1, team2, fallback_winner)
            if explicit:
                return explicit
            return None
        # Snapshot legs are stored in (team1_goals, team2_goals) order for both
        # legs, so aggregate totals are a straight sum.
        team1_total = leg1[0] + leg2[0]
        team2_total = leg1[1] + leg2[1]
        if team1_total > team2_total:
            return team1
        if team2_total > team1_total:
            return team2
    explicit = _team_from_advancer(team1, team2, advancer)
    if explicit:
        return explicit
    explicit = _team_from_advancer(team1, team2, fallback_winner)
    if explicit:
        return explicit
    return None


def _round_bonus(competition: str, round_name: str) -> float:
    bonus_round = _extract_round_bonus_round(round_name)
    if bonus_round is None:
        return 0.0
    return knockout_progression_bonus(competition, bonus_round)


def _award_bonus_for_teams(
    club_totals: dict[str, float],
    competition: str,
    round_name: str,
    teams: Iterable[str],
    *,
    awarded: set[tuple[str, str, str]] | None = None,
) -> None:
    bonus_round = _extract_round_bonus_round(round_name)
    if bonus_round is None:
        return
    bonus = knockout_progression_bonus(competition, bonus_round)
    for team in teams:
        if team:
            club_id = _club_id(team)
            key = (competition, bonus_round, club_id)
            if awarded is not None:
                if key in awarded:
                    continue
                awarded.add(key)
            club_totals[club_id] += bonus


def _next_round_name(round_name: str) -> str | None:
    if round_name == "R16":
        return "QF"
    if round_name == "QF":
        return "SF"
    if round_name == "SF":
        return "F"
    return None


def _process_knockout_tie(
    competition: str,
    round_name: str,
    tie: Mapping[str, Any],
    club_totals: dict[str, float],
    club_names: dict[str, str],
    club_associations: dict[str, str],
    override_map: Mapping[str, MatchOverride] | None,
    progression_awarded: set[tuple[str, str, str]],
    *,
    award_round_bonus: bool,
) -> str | None:
    team1 = tie.get("team1")
    team2 = tie.get("team2")
    if not team1 or not team2:
        return None

    assoc1 = tie.get("team1_country", "")
    assoc2 = tie.get("team2_country", "")
    team1_id = _club_id(team1)
    team2_id = _club_id(team2)
    club_names.setdefault(team1_id, team1)
    club_names.setdefault(team2_id, team2)
    club_associations.setdefault(team1_id, assoc1)
    club_associations.setdefault(team2_id, assoc2)
    club_totals.setdefault(team1_id, 0.0)
    club_totals.setdefault(team2_id, 0.0)

    leg1_base = tie.get("leg1")
    leg2_base = None if round_name == "F" else tie.get("leg2")
    leg1_override = _lookup_override(
        override_map,
        competition,
        round_name,
        team1,
        team2,
        1,
        base_score=leg1_base,
    )
    leg2_override = _lookup_override(
        override_map,
        competition,
        round_name,
        team1,
        team2,
        2,
        base_score=leg2_base,
    )

    leg1 = _score_pair(leg1_override) or _score_pair(leg1_base)
    leg2 = _score_pair(leg2_override) or _score_pair(leg2_base)

    if leg1 is not None:
        _apply_match_score(
            club_totals,
            club_names,
            club_associations,
            team1,
            assoc1,
            team2,
            assoc2,
            leg1[0],
            leg1[1],
            stage="final" if round_name == "F" else "knockout",
        )

    if leg2 is not None:
        _apply_match_score(
            club_totals,
            club_names,
            club_associations,
            team1,
            assoc1,
            team2,
            assoc2,
            leg2[0],
            leg2[1],
            stage="final" if round_name == "F" else "knockout",
        )

    fallback_winner = tie.get("winner")
    locked_winner = _team_from_advancer(team1, team2, fallback_winner)
    override_advancer = None
    if locked_winner is None:
        override_advancer = (
            (leg1_override.advancer if leg1_override and leg1_override.advancer else None)
            or (leg2_override.advancer if leg2_override and leg2_override.advancer else None)
        )

    winner = _determine_tie_winner(
        team1,
        team2,
        leg1,
        leg2,
        single_leg=round_name == "F",
        advancer=override_advancer,
        fallback_winner=fallback_winner,
    )

    if award_round_bonus:
        _award_bonus_for_teams(
            club_totals,
            competition,
            round_name,
            (team1, team2),
            awarded=progression_awarded,
        )

    next_round = _next_round_name(round_name)
    if next_round and winner:
        _award_bonus_for_teams(
            club_totals,
            competition,
            next_round,
            (winner,),
            awarded=progression_awarded,
        )

    return winner


def _pairwise(items: list[str | None]) -> list[tuple[str | None, str | None]]:
    pairs: list[tuple[str | None, str | None]] = []
    for index in range(0, len(items), 2):
        team1 = items[index]
        team2 = items[index + 1] if index + 1 < len(items) else None
        if team1 or team2:
            pairs.append((team1, team2))
    return pairs


def _pair_key(team1: str, team2: str) -> tuple[str, str]:
    """Build an order-insensitive key for a knockout tie."""
    first = _normalize_id(team1)
    second = _normalize_id(team2)
    return (first, second) if first <= second else (second, first)


def _find_tie(
    ties: list[Mapping[str, Any]],
    team1: str,
    team2: str,
) -> tuple[Mapping[str, Any] | None, bool]:
    """Find a snapshot tie for the given pair of teams.

    Returns the matching tie and a flag indicating whether the snapshot order
    matches the requested order. If the teams were stored in reverse order in
    the snapshot, the caller can swap the score pairs before rendering or
    applying overrides.
    """
    requested = _pair_key(team1, team2)
    requested_team1 = _normalize_id(team1)
    for tie in ties:
        tie_team1 = tie.get("team1")
        tie_team2 = tie.get("team2")
        if not tie_team1 or not tie_team2:
            continue
        if _pair_key(tie_team1, tie_team2) != requested:
            continue
        same_order = _normalize_id(tie_team1) == requested_team1
        return tie, same_order
    return None, True


def _reverse_score_pair(score: Any) -> list[int] | None:
    pair = _score_pair(score)
    if pair is None:
        return None
    return [pair[1], pair[0]]


def _build_derived_tie(
    competition: str,
    round_name: str,
    left: str | None,
    right: str | None,
    club_associations: Mapping[str, str],
    snapshot_ties: list[Mapping[str, Any]] | None = None,
) -> Mapping[str, Any]:
    """Build a tie for the next round from previous-round winners."""
    tie: dict[str, Any] = {
        "team1": left or "",
        "team2": right or "",
        "team1_country": club_associations.get(_club_id(left), "") if left else "",
        "team2_country": club_associations.get(_club_id(right), "") if right else "",
    }
    if snapshot_ties:
        actual_tie, same_order = _find_tie(snapshot_ties, left, right)
        if actual_tie is not None:
            tie["leg1"] = actual_tie.get("leg1")
            if round_name != "F":
                tie["leg2"] = actual_tie.get("leg2")
            tie["winner"] = actual_tie.get("winner")
            if not same_order:
                tie["leg1"] = _reverse_score_pair(tie["leg1"])
                if round_name != "F":
                    tie["leg2"] = _reverse_score_pair(tie["leg2"])
    return tie


def simulate(
    snapshot: Mapping[str, Any],
    overrides: Iterable[MatchOverride] | Mapping[str, MatchOverride] | None = None,
) -> SimulationResult:
    """
    Simulate the current season from the cached snapshot.

    The snapshot already contains completed results. Overrides can replace or
    supplement individual tie legs later when the UI starts collecting what-if
    inputs.
    """
    override_map: Mapping[str, MatchOverride] | None
    if overrides is None or isinstance(overrides, Mapping):
        override_map = overrides
    else:
        override_map = {
            make_match_key(item.competition, item.round_name, item.team1, item.team2, item.leg): item
            for item in overrides
        }

    club_totals: dict[str, float] = {}
    club_names: dict[str, str] = {}
    club_associations: dict[str, str] = {}
    progression_awarded: set[tuple[str, str, str]] = set()

    def register_club(team: str, association: str) -> str:
        club_id = _club_id(team)
        club_names.setdefault(club_id, team)
        club_associations.setdefault(club_id, association)
        club_totals.setdefault(club_id, 0.0)
        return club_id

    processed_keys: set[str] = set()

    for competition, comp_data in _iter_competitions(snapshot):
        # League phase standings
        for row in comp_data.get("league_phase", []) or []:
            team = row.get("team")
            association = row.get("country", "")
            if not team:
                continue
            club_id = register_club(team, association)
            wins = int(row.get("W", 0) or 0)
            draws = int(row.get("D", 0) or 0)
            club_totals[club_id] += wins * 2.0 + draws * 1.0
            position = row.get("position")
            if isinstance(position, int):
                club_totals[club_id] += league_phase_bonus(competition, position)

        # Qualifying ties
        for round_name, ties in (comp_data.get("qualifying", {}) or {}).items():
            for tie in ties or []:
                team1 = tie.get("team1")
                team2 = tie.get("team2")
                if not team1 or not team2:
                    continue
                assoc1 = tie.get("team1_country", "")
                assoc2 = tie.get("team2_country", "")
                register_club(team1, assoc1)
                register_club(team2, assoc2)

                round_override_leg1 = _lookup_override(
                    override_map, competition, round_name, team1, team2, 1
                )
                round_override_leg2 = _lookup_override(
                    override_map, competition, round_name, team1, team2, 2
                )

                leg1 = _score_pair(round_override_leg1) or _score_pair(tie.get("leg1"))
                leg2 = _score_pair(round_override_leg2) or _score_pair(tie.get("leg2"))

                if leg1 is not None:
                    processed_keys.add(make_match_key(competition, round_name, team1, team2, 1))
                    _apply_match_score(
                        club_totals,
                        club_names,
                        club_associations,
                        team1,
                        assoc1,
                        team2,
                        assoc2,
                        leg1[0],
                        leg1[1],
                        stage="qualifying",
                    )
                if leg2 is not None:
                    processed_keys.add(make_match_key(competition, round_name, team1, team2, 2))
                    _apply_match_score(
                        club_totals,
                        club_names,
                        club_associations,
                        team1,
                        assoc1,
                        team2,
                        assoc2,
                        leg2[0],
                        leg2[1],
                        stage="qualifying",
                    )

        knockout = comp_data.get("knockout", {}) or {}
        round_order = ["KPO", "R16"]
        for round_name in round_order:
            for tie in knockout.get(round_name) or []:
                _process_knockout_tie(
                    competition,
                    round_name,
                    tie,
                    club_totals,
                    club_names,
                    club_associations,
                    override_map,
                    progression_awarded,
                    award_round_bonus=round_name == "R16",
                )

        previous_winners: list[str | None] | None = None

        for round_name in ["QF", "SF", "F"]:
            snapshot_ties = list(knockout.get(round_name) or [])
            ties_to_process: list[Mapping[str, Any]] = []
            if round_name == "QF":
                ties_to_process = snapshot_ties
                if not ties_to_process and previous_winners is not None:
                    ties_to_process = [
                        _build_derived_tie(
                            competition,
                            round_name,
                            team1,
                            team2,
                            club_associations,
                            snapshot_ties,
                        )
                        for team1, team2 in _pairwise(previous_winners)
                    ]
                if not ties_to_process:
                    continue
            elif previous_winners is None:
                if not snapshot_ties:
                    continue
                ties_to_process = snapshot_ties
            else:
                ties_to_process = [
                    _build_derived_tie(
                        competition,
                        round_name,
                        team1,
                        team2,
                        club_associations,
                        snapshot_ties,
                    )
                    for team1, team2 in _pairwise(previous_winners)
                ]
                if not ties_to_process:
                    continue

            round_winners: list[str | None] = []
            for tie in ties_to_process:
                winner = _process_knockout_tie(
                    competition,
                    round_name,
                    tie,
                    club_totals,
                    club_names,
                    club_associations,
                    override_map,
                    progression_awarded,
                    award_round_bonus=round_name in {"R16", "QF", "SF", "F"},
                )
                round_winners.append(winner)

            previous_winners = round_winners

    club_summaries = [
        ClubSeasonSummary(
            club_id=club_id,
            club_name=club_names.get(club_id, club_id),
            association_id=club_associations.get(club_id, ""),
            points=truncate_to_thousandth(points),
        )
        for club_id, points in club_totals.items()
    ]

    club_summaries.sort(
        key=lambda club: (
            -club.points,
            club.club_name.lower(),
            club.club_id,
        )
    )

    association_rankings = _build_association_rankings(club_summaries)

    top_two = (
        association_rankings[0].association_name if len(association_rankings) > 0 else "",
        association_rankings[1].association_name if len(association_rankings) > 1 else "",
    )
    leader = top_two[0] if top_two[0] else ""

    return SimulationResult(
        association_rankings=association_rankings,
        club_rankings=club_summaries,
        fifth_champions_league_spot_holder=leader,
        extra_ucl_spot_associations=top_two,
    )
