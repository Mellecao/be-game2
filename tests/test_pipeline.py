# tests/test_pipeline.py
import time
import pytest
from unittest.mock import patch, MagicMock


def _make_task(card_id="card-1", name="Teste Card"):
    from server.planner_loop import PlannerTask
    return PlannerTask(
        id=card_id, card_name=name,
        status="delegating", step=0, log="",
        created_at=time.time(), start_at=time.time(),
    )


def _mock_result(text: str) -> MagicMock:
    m = MagicMock()
    m.__str__ = lambda _: text
    return m


def test_pipeline_completes_all_7_steps(monkeypatch):
    """Pipeline feliz: todos os 7 passos completam, status final = done."""
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list"), \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"):

        mock_crew_cls.return_value.kickoff.return_value = _mock_result(
            "https://github.com/v27me/teste-card"
        )
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "Briefing do teste")

    assert task.status == "done"
    assert task.step == 7


def test_pipeline_aborts_when_qa_reprovado_twice(monkeypatch):
    """QA reprova duas vezes (primeira passagem + pos-revisao) → pipeline aborta com status error."""
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    call_count = {"n": 0}

    def mock_kickoff():
        call_count["n"] += 1
        # Call 5 = QA primeira passagem, call 7 = QA segunda passagem (apos revisao Dev)
        if call_count["n"] in (5, 7):
            return _mock_result("STATUS: REPROVADO — falta viewport meta")
        return _mock_result("OK resultado")

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list") as mock_move, \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "")

    assert task.status == "error"
    assert "REPROVADO" in task.log
    mock_move.assert_not_called()


def test_pipeline_continues_when_qa_approves_after_revision(monkeypatch):
    """QA reprova na primeira passagem mas aprova apos revisao → pipeline conclui normalmente."""
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    call_count = {"n": 0}

    def mock_kickoff():
        call_count["n"] += 1
        if call_count["n"] == 5:
            return _mock_result("STATUS: REPROVADO — falta viewport meta")
        return _mock_result("github: https://github.com/v27me/teste-card\nnetlify: https://teste-card.netlify.app")

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list"), \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "Briefing")

    assert task.status == "done"
    assert task.step == 7


def test_pipeline_respects_cancellation(monkeypatch):
    """Task cancelada durante o pipeline para antes do proximo passo."""
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    task = _make_task()

    call_count = {"n": 0}

    def mock_kickoff():
        call_count["n"] += 1
        if call_count["n"] == 2:
            task.status = "cancelled"
        return _mock_result("resultado")

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "")

    assert task.status == "cancelled"
