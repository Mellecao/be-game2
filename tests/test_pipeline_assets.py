# tests/test_pipeline_assets.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_pipeline_status_enum_includes_new_steps():
    """Verifica que os novos status estao mapeados em planner_loop.py."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    for status in ["imagining", "reviewing_assets", "regen_assets", "modeling_3d", "curating"]:
        assert status in src, f"status '{status}' nao referenciado em planner_loop.py"


def test_curation_runs_in_finally_even_on_error():
    """Verifica que _run_curation eh chamado dentro do bloco finally de _run_pipeline."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    # _run_curation deve aparecer dentro de bloco `finally:` em _run_pipeline
    finally_idx = src.find("finally:")
    curation_idx = src.find("_run_curation")
    assert finally_idx > 0, "bloco finally: nao encontrado em planner_loop.py"
    assert curation_idx > 0, "_run_curation nao encontrado em planner_loop.py"
    assert curation_idx > finally_idx, "_run_curation deve estar depois de finally: no arquivo"


def test_set_helper_uses_10_step_format():
    """Verifica que _set usa [N/10] e nao [N/7]."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    assert "[{step_num}/10]" in src, "_set deve usar formato [N/10]"
    assert "[{step_num}/7]" not in src, "[N/7] antigo deve ter sumido"


def test_pipeline_has_10_steps_total():
    """Verifica que o pipeline referencia etapas 1-10 e 7,8,9,10 explicitamente."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    # Etapas esperadas: _set(1,...), _set(2,...), ..., _set(10,...)
    for step in range(1, 11):
        assert f"_set({step}," in src, f"_set({step}, ...) nao encontrado — pipeline nao tem 10 etapas"


def test_run_curation_function_exists():
    """Verifica que _run_curation existe como funcao no modulo."""
    from server import planner_loop
    assert hasattr(planner_loop, "_run_curation"), "_run_curation deve ser funcao do modulo"
    import inspect
    assert callable(planner_loop._run_curation), "_run_curation deve ser callable"


def test_pipeline_logger_set_active_slug_called():
    """Verifica que pipeline_logger.set_active_slug e chamado em _run_pipeline."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    assert "pipeline_logger.set_active_slug(slug)" in src, \
        "pipeline_logger.set_active_slug(slug) deve ser chamado em _run_pipeline"
    assert "pipeline_logger.set_active_slug(None)" in src, \
        "pipeline_logger.set_active_slug(None) deve ser chamado no finally"


def test_step_start_event_logged_in_set():
    """Verifica que _set chama pipeline_logger.log_event com step_start."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    assert 'pipeline_logger.log_event(None, "step_start"' in src, \
        '_set deve chamar pipeline_logger.log_event(None, "step_start", ...)'


def test_new_agents_imported_in_run_pipeline():
    """Verifica que create_image_artist, create_designer_reviewer, create_3d_artist sao importados."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    for agent_fn in ["create_image_artist", "create_designer_reviewer", "create_3d_artist"]:
        assert agent_fn in src, f"{agent_fn} nao encontrado em planner_loop.py"


def test_new_tasks_imported_in_run_pipeline():
    """Verifica que as novas task factories sao importadas."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    for task_fn in [
        "create_image_pipeline_task",
        "create_designer_review_task",
        "create_3d_pipeline_task",
        "create_curator_finalize_task",
    ]:
        assert task_fn in src, f"{task_fn} nao encontrado em planner_loop.py"


def test_curation_phase_sets_curating_status():
    """Verifica que _run_curation seta status 'curating' e restaura final_status."""
    from server import planner_loop
    src = Path(planner_loop.__file__).read_text(encoding="utf-8")
    # A funcao _run_curation deve setar status curating
    curation_start = src.find("def _run_curation")
    assert curation_start > 0, "_run_curation nao encontrado"
    curation_body = src[curation_start:]
    assert '"curating"' in curation_body, \
        '_run_curation deve setar task.status = "curating"'
    assert "final_status" in curation_body, \
        '_run_curation deve restaurar task.status = final_status'
