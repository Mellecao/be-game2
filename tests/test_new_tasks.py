def test_designer_task_requires_manifest():
    from server.agents import create_designer
    from server.tasks import create_designer_task
    designer = create_designer()
    task = create_designer_task(designer, {"slug": "x", "copy_path": "p.md"})
    assert "asset_manifest" in task.description


def test_image_pipeline_task_mentions_manifest_iter():
    from server.agents import create_image_artist
    from server.tasks import create_image_pipeline_task
    a = create_image_artist()
    t = create_image_pipeline_task(a, {"slug": "x", "manifest": {"images": []}})
    assert "flux_image" in t.description


def test_3d_pipeline_task_filters_convert_to_3d():
    from server.agents import create_3d_artist
    from server.tasks import create_3d_pipeline_task
    a = create_3d_artist()
    t = create_3d_pipeline_task(a, {"slug": "x"})
    assert "convert_to_3d" in t.description


def test_designer_review_task_requires_json_output():
    from server.agents import create_designer_reviewer
    from server.tasks import create_designer_review_task
    a = create_designer_reviewer()
    t = create_designer_review_task(a, {"slug": "x", "manifest_resolved": {"images": []}, "guide_excerpt": ""})
    assert "JSON" in t.description and "verdict" in t.description


def test_curator_finalize_task_includes_log_path():
    from server.agents import create_bibliotecario
    from server.tasks import create_curator_finalize_task
    a = create_bibliotecario()
    t = create_curator_finalize_task(a, {
        "slug": "x", "moc_path": "Atlas/Maps/x MOC.md",
        "effort_path": "Efforts/On/x (E).md", "final_status": "done",
        "log_path": "output/x/.pipeline.log",
    })
    assert "pipeline_log" in t.description
    assert "ACE" in t.description or "Atlas" in t.description


def test_create_creative_brief_task_includes_slug_and_briefing():
    from server.tasks import create_creative_brief_task
    from crewai import Task
    task = create_creative_brief_task({
        "slug": "fintech-x",
        "card_name": "Fintech X Landing",
        "card_desc": "Landing pra produto B2B SaaS fintech.",
    })
    assert isinstance(task, Task)
    assert "fintech-x" in task.description
    assert "Fintech X Landing" in task.description or "Landing pra produto B2B" in task.description
