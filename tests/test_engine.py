from __future__ import annotations

from backend.data import load_dataset
from backend.simulation import MatchOverride, simulate


def _assoc(result, name: str):
    return next(row for row in result.association_rankings if row.association_name == name)


def _first_tie(snapshot: dict, round_name: str, *, require_played_leg2: bool) -> dict:
    ties = snapshot["ucl"]["knockout"][round_name]
    for tie in ties:
        if bool(tie.get("leg2_played")) == require_played_leg2:
            return tie
    raise AssertionError(f"Could not find tie for {round_name} (require_played_leg2={require_played_leg2})")


def main() -> None:
    snapshot = load_dataset()
    base = simulate(snapshot)

    # Basic sanity: top associations should exist in the dataset.
    for name in ["England", "Spain", "Italy", "Germany", "France"]:
        _assoc(base, name)

    # Played legs are locked: score overrides must not change totals.
    qf_tie = _first_tie(snapshot, "QF", require_played_leg2=True)
    locked_home = qf_tie["team1_country"]
    locked_away = qf_tie["team2_country"]
    locked_before = sum(a.total_points for a in base.association_rankings)
    locked_override = simulate(
        snapshot,
        [
            MatchOverride(
                competition="UCL",
                round_name="QF",
                team1=qf_tie["team1"],
                team2=qf_tie["team2"],
                leg=1,
                home_score=0,
                away_score=0,
            )
        ],
    )
    locked_after = sum(a.total_points for a in locked_override.association_rankings)
    assert locked_after == locked_before, (locked_before, locked_after)
    assert _assoc(locked_override, locked_home).total_points == _assoc(base, locked_home).total_points
    assert _assoc(locked_override, locked_away).total_points == _assoc(base, locked_away).total_points

    # Unplayed legs are editable: score overrides should change totals.
    sf_tie = _first_tie(snapshot, "SF", require_played_leg2=False)
    editable_before = sum(a.total_points for a in base.association_rankings)
    editable_override = simulate(
        snapshot,
        [
            MatchOverride(
                competition="UCL",
                round_name="SF",
                team1=sf_tie["team1"],
                team2=sf_tie["team2"],
                leg=1,
                home_score=1,
                away_score=0,
            )
        ],
    )
    editable_after = sum(a.total_points for a in editable_override.association_rankings)
    assert editable_after != editable_before, (editable_before, editable_after)

    print("engine checks passed")


if __name__ == "__main__":
    main()
