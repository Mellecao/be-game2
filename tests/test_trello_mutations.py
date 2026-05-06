# tests/test_trello_mutations.py
import os
import pytest


def test_move_card_calls_correct_endpoint(requests_mock):
    os.environ.setdefault("TRELLO_API_KEY", "fakekey")
    os.environ.setdefault("TRELLO_TOKEN",   "faketoken")

    adapter = requests_mock.put("https://api.trello.com/1/cards/card123", json={"id": "card123"})

    from server.trello_tool import move_card_to_list
    move_card_to_list("card123", "list456")

    assert adapter.called
    # requests_mock lowercases query-string keys in .qs
    assert "idlist" in adapter.last_request.qs
    assert adapter.last_request.qs["idlist"][0] == "list456"


def test_update_card_description_calls_correct_endpoint(requests_mock):
    os.environ.setdefault("TRELLO_API_KEY", "fakekey")
    os.environ.setdefault("TRELLO_TOKEN",   "faketoken")

    adapter = requests_mock.put("https://api.trello.com/1/cards/card789", json={"id": "card789"})

    from server.trello_tool import update_card_description
    update_card_description("card789", "Nova descricao com URL")

    assert adapter.called
    assert "desc" in adapter.last_request.qs


def test_move_card_raises_on_http_error(requests_mock):
    os.environ.setdefault("TRELLO_API_KEY", "fakekey")
    os.environ.setdefault("TRELLO_TOKEN",   "faketoken")

    requests_mock.put("https://api.trello.com/1/cards/bad", status_code=401, text="Unauthorized")

    from server.trello_tool import move_card_to_list
    with pytest.raises(Exception):
        move_card_to_list("bad", "list")
