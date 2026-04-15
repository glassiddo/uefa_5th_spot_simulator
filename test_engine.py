from __future__ import annotations

from backend.data import load_dataset
from backend.simulation import MatchOverride, simulate


def _assoc(result, name: str):
    return next(row for row in result.association_rankings if row.association_name == name)


def main() -> None:
    snapshot = load_dataset()
    base = simulate(snapshot)

    expected = {
        "Belgium": 11.4,
        "Poland": 15.75,
        "Norway": 8.05,
        "Austria": 4.1,
        "Croatia": 7.031,
        "Serbia": 5.75,
        "Slovakia": 2.625,
        "Faroe Islands": 1.75,
    }
    for name, points in expected.items():
        assoc = _assoc(base, name)
        assert assoc.average_points == points, (name, assoc.average_points, points)

    locked_override = simulate(
        snapshot,
        [
            MatchOverride(
                competition="UCL",
                round_name="QF",
                team1="Paris Saint-Germain",
                team2="Liverpool",
                leg=1,
                home_score=0,
                away_score=0,
            )
        ],
    )
    assert _assoc(locked_override, "France").total_points == _assoc(base, "France").total_points
    assert _assoc(locked_override, "England").total_points == _assoc(base, "England").total_points

    editable_override = simulate(
        snapshot,
        [
            MatchOverride(
                competition="UCL",
                round_name="QF",
                team1="Real Madrid",
                team2="Bayern Munich",
                leg=2,
                advancer="Real Madrid",
            )
        ],
    )
    spain_delta = _assoc(editable_override, "Spain").total_points - _assoc(base, "Spain").total_points
    assert spain_delta == 1.5, spain_delta

    print("engine checks passed")


if __name__ == "__main__":
    main()
