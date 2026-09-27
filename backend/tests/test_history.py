import json
import logging

from blokus.history import DATA_DIR_ENV, GameHistory
from blokus.testing import make_record


def test_memory_only_history():
    history = GameHistory(None)
    first, second = make_record(("A", 0), ("B", -5), minutes=5), make_record(("A", -5), ("B", 0))
    history.add(first)
    history.add(second)
    history.add(first)
    assert history.records() == (second, first)
    assert {r.identity for r in history.ratings()} == {"A", "B"}


def test_games_are_saved_per_run_and_month_and_reloaded(tmp_path):
    history = GameHistory(tmp_path, run_id="run-1")
    records = [make_record(("A", 0), ("B", -5), minutes=m) for m in (0, 1)]
    for record in records:
        history.add(record)
    path = tmp_path / "games" / "2026-09" / "run-1.jsonl"
    lines = path.read_text().splitlines()
    assert [json.loads(line)["id"] for line in lines] == [r.id for r in records]

    later = GameHistory(tmp_path, run_id="run-2")
    assert later.records() == tuple(records)
    later.add(make_record(("A", -5), ("B", 0), minutes=120))
    october = make_record(("C", 0), ("B", -1), minutes=60 * 24 * 30)
    later.add(october)
    assert path.read_text().splitlines() == lines  # run 1's file is never touched again
    assert (tmp_path / "games" / "2026-09" / "run-2.jsonl").exists()
    assert (tmp_path / "games" / "2026-10" / "run-2.jsonl").read_text().count("\n") == 1

    reloaded = GameHistory(tmp_path)
    assert len(reloaded.records()) == 4
    assert reloaded.records()[-1] == october
    assert reloaded.ratings() == later.ratings()


def test_bad_lines_and_duplicates_are_skipped(tmp_path, caplog):
    good = make_record(("A", 0), ("B", -5))
    folder = tmp_path / "games" / "2026-09"
    folder.mkdir(parents=True)
    line = json.dumps(good.to_json())
    (folder / "a.jsonl").write_text(f"{line}\nnot json\n\n{json.dumps({'version': 7})}\n")
    (folder / "b.jsonl").write_text(line + "\n")
    with caplog.at_level(logging.WARNING):
        history = GameHistory(tmp_path)
    assert history.records() == (good,)
    assert "a.jsonl line 2" in caplog.text and "a.jsonl line 4" in caplog.text


def test_a_failed_save_is_logged_and_the_game_still_counts(tmp_path, caplog):
    root = tmp_path / "not-a-folder"
    root.write_text("")
    history = GameHistory(root)
    with caplog.at_level(logging.ERROR):
        history.add(make_record(("A", 0), ("B", -5)))
    assert "Could not save game" in caplog.text
    assert len(history.records()) == 1


def test_data_dir_from_the_environment(tmp_path):
    assert GameHistory.from_env({DATA_DIR_ENV: str(tmp_path)}).root == tmp_path
    assert str(GameHistory.from_env({}).root) == "data"
