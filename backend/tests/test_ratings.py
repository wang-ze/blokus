import pytest

from blokus.ratings import INITIAL_RATING, K_FACTOR, expected_score, ratings
from blokus.testing import make_record


def by_identity(table):
    return {r.identity: r for r in table}


def test_expected_scores_are_complementary():
    assert expected_score(1500, 1500) == 0.5
    assert expected_score(1700, 1500) + expected_score(1500, 1700) == pytest.approx(1)
    assert expected_score(1900, 1500) == pytest.approx(10 / 11)


def test_a_two_player_win_moves_half_of_k():
    table = by_identity(ratings([make_record(("Greedy", -30), ("Tactician", -10))]))
    assert table["Tactician"].rating == INITIAL_RATING + K_FACTOR / 2
    assert table["Greedy"].rating == INITIAL_RATING - K_FACTOR / 2
    assert (table["Tactician"].wins, table["Greedy"].wins) == (1, 0)
    assert table["Tactician"].games == table["Greedy"].games == 1


def test_a_draw_between_equals_changes_nothing_and_counts_as_a_win_for_both():
    table = by_identity(ratings([make_record(("Greedy", -20), ("Tactician", -20))]))
    assert table["Greedy"].rating == table["Tactician"].rating == INITIAL_RATING
    assert table["Greedy"].wins == table["Tactician"].wins == 1


def test_four_player_games_rank_everyone_and_conserve_points():
    record = make_record(("A", 5), ("B", -3), ("C", -3), ("D", -40))
    table = ratings([record])
    assert [r.identity for r in table[:1]] == ["A"]
    assert table[-1].identity == "D"
    assert sum(r.rating for r in table) == pytest.approx(4 * INITIAL_RATING)
    # The winner beat 3 equal opponents: 3 pairings of K/3 * (1 - 0.5).
    assert by_identity(table)["A"].rating == pytest.approx(INITIAL_RATING + K_FACTOR / 2)
    assert by_identity(table)["B"].rating == by_identity(table)["C"].rating


def test_two_seats_with_the_same_identity_are_not_compared_with_each_other():
    record = make_record(("model", 0, "llm"), ("Greedy", -10), ("model", -20, "llm"), ("T", -30))
    table = by_identity(ratings([record]))
    model = table["model"]
    assert model.games == 1 and model.wins == 1
    # Seat 1 beats Greedy and T, seat 3 loses to Greedy and beats T: +1 -> 3 wins, 1 loss.
    step = K_FACTOR / 3
    assert model.rating == pytest.approx(INITIAL_RATING + step * (3 - 4 * 0.5))
    assert sum(r.rating for r in table.values()) == pytest.approx(3 * INITIAL_RATING)


def test_kinds_keep_identities_apart():
    table = ratings([make_record(("Human", 0, "human"), ("Human", -5, "bot"))])
    assert {(r.kind, r.identity) for r in table} == {("human", "Human"), ("bot", "Human")}


def test_games_are_replayed_in_time_order():
    early = make_record(("A", 0), ("B", -10), minutes=0)
    late = make_record(("A", -10), ("B", 0), minutes=5)
    assert ratings([late, early]) == ratings([early, late])
    table = by_identity(ratings([early, late]))
    # Losing the second game costs A more than it gained, because A was the favorite by then.
    assert table["A"].rating < INITIAL_RATING < table["B"].rating
    assert table["A"].last_played == late.finished_at


def test_best_first_then_most_games():
    records = [
        make_record(("A", 0), ("B", -1), minutes=0),
        make_record(("C", 0), ("D", 0), minutes=1),
        make_record(("C", 0), ("D", 0), minutes=2),
    ]
    assert [r.identity for r in ratings(records)] == ["A", "C", "D", "B"]
    assert ratings([]) == []
