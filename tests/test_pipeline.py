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


def test_pipeline_completes_all_10_steps(monkeypatch):
    """Pipeline feliz: todos os 10 passos completam, status final = done.

    Sequencia de kickoffs apos refactor (Crew Criativo + Crew QA):
      1. planner MOC      2. creative_crew      3. dev
      4. qa_crew (APROVADO)   5. devops            6. planner_close
      7. curator (post-pipeline)
    """
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    call_count = {"n": 0}

    def mock_kickoff():
        call_count["n"] += 1
        # call 4 = qa_crew (precisa retornar APROVADO)
        if call_count["n"] == 4:
            return _mock_result('{"verdict": "APROVADO", "report_path": "x"}')
        # call 5 = devops (devolve URL pra DevOps parser)
        if call_count["n"] == 5:
            return _mock_result(
                "github: https://github.com/v27me/teste-card\n"
                "netlify: https://teste-card.netlify.app"
            )
        return _mock_result("OK resultado")

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list"), \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_design"), \
         patch("server.librarian.after_assets"), \
         patch("server.librarian.after_research"), \
         patch("server.librarian.after_qa_visual"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"), \
         patch("server.pipeline_logger.set_active_slug"), \
         patch("server.pipeline_logger.log_event"), \
         patch("server.pipeline_logger.read_log", return_value=[]):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "Briefing do teste")

    assert task.status == "done"
    assert task.step == 10


def test_pipeline_aborts_when_qa_reprovado_max_retries(monkeypatch):
    """Crew QA reprova todas as tentativas → status final = qa_blocked.

    Sem fix_prompt.md gerado, o loop sai apos a primeira reprovacao
    (event_bus.emit warn + break). verdict permanece REPROVADO →
    final_status = qa_blocked.
    """
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    def mock_kickoff():
        # Sem APROVADO/STATUS: APROVADO no output, _parse_qa_verdict cai em REPROVADO.
        return _mock_result('{"verdict": "REPROVADO", "report_path": "x"}')

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list") as mock_move, \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_design"), \
         patch("server.librarian.after_assets"), \
         patch("server.librarian.after_research"), \
         patch("server.librarian.after_qa_visual"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"), \
         patch("server.pipeline_logger.set_active_slug"), \
         patch("server.pipeline_logger.log_event"), \
         patch("server.pipeline_logger.read_log", return_value=[]):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "")

    assert task.status == "qa_blocked"
    assert "QA bloqueou" in task.log
    mock_move.assert_not_called()


def test_pipeline_continues_when_qa_approves_first_attempt(monkeypatch):
    """Crew QA aprova na primeira tentativa → pipeline conclui normalmente."""
    monkeypatch.setenv("TRELLO_DONE_LIST_ID", "list-done")
    monkeypatch.setenv("TRELLO_API_KEY", "fakekey")
    monkeypatch.setenv("TRELLO_TOKEN", "faketoken")
    monkeypatch.setenv("TRELLO_LIST_ID", "fakelist")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-or-key")

    call_count = {"n": 0}

    def mock_kickoff():
        call_count["n"] += 1
        if call_count["n"] == 4:
            return _mock_result('{"verdict": "APROVADO"}')
        return _mock_result(
            "github: https://github.com/v27me/teste-card\n"
            "netlify: https://teste-card.netlify.app"
        )

    with patch("server.planner_loop.Crew") as mock_crew_cls, \
         patch("server.vault_writer.write_note", return_value=MagicMock()), \
         patch("server.trello_tool.move_card_to_list"), \
         patch("server.trello_tool.update_card_description"), \
         patch("server.librarian.after_copy"), \
         patch("server.librarian.after_design"), \
         patch("server.librarian.after_assets"), \
         patch("server.librarian.after_research"), \
         patch("server.librarian.after_qa_visual"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"), \
         patch("server.pipeline_logger.set_active_slug"), \
         patch("server.pipeline_logger.log_event"), \
         patch("server.pipeline_logger.read_log", return_value=[]):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff
        task = _make_task()

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "Briefing")

    assert task.status == "done"
    assert task.step == 10


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
         patch("server.librarian.after_design"), \
         patch("server.librarian.after_assets"), \
         patch("server.librarian.after_research"), \
         patch("server.librarian.after_qa_visual"), \
         patch("server.librarian.after_dev"), \
         patch("server.librarian.after_deploy"), \
         patch("server.pipeline_logger.set_active_slug"), \
         patch("server.pipeline_logger.log_event"), \
         patch("server.pipeline_logger.read_log", return_value=[]):

        mock_crew_cls.return_value.kickoff.side_effect = mock_kickoff

        from server.planner_loop import _run_pipeline
        _run_pipeline(task, "Teste Card", "")

    # curadoria roda mas restaura o status cancelled
    assert task.status == "cancelled"
