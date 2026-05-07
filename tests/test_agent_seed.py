def test_agent_seed_has_new_npcs():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "image_artist" in ids
    assert "agente_3d" in ids


def test_agent_seed_positions_around_designer():
    from server.api import AGENT_SEED
    by_id = {a["id"]: a for a in AGENT_SEED}
    assert by_id["image_artist"]["col"] == 1.0
    assert by_id["image_artist"]["row"] == 4.0
    assert by_id["agente_3d"]["col"] == 3.0
    assert by_id["agente_3d"]["row"] == 4.0


def test_agent_seed_has_unique_ids():
    from server.api import AGENT_SEED
    ids = [a["id"] for a in AGENT_SEED]
    assert len(ids) == len(set(ids))


def test_agent_seed_has_secretario():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "secretario" in ids


def test_agent_seed_has_bibliotecario():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "bibliotecario" in ids


def test_agent_display_has_new_npcs():
    from server.api import _AGENT_DISPLAY
    assert _AGENT_DISPLAY.get("secretario") == "Secretário"
    assert _AGENT_DISPLAY.get("bibliotecario") == "Bibliotecário"
