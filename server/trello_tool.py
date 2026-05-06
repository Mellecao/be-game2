import os
import requests
from crewai.tools import BaseTool
from pydantic import Field


class TrelloListCardsTool(BaseTool):
    name: str = "trello_list_cards"
    description: str = (
        "Busca todos os cards da lista TO-DO no Trello. "
        "Retorna nome, descrição e ID de cada card pendente."
    )
    api_key: str = Field(default_factory=lambda: os.environ["TRELLO_API_KEY"])
    token: str = Field(default_factory=lambda: os.environ["TRELLO_TOKEN"])
    list_id: str = Field(default_factory=lambda: os.environ["TRELLO_LIST_ID"])

    def _run(self, *args, **kwargs) -> str:
        url = f"https://api.trello.com/1/lists/{self.list_id}/cards"
        params = {"key": self.api_key, "token": self.token, "fields": "name,desc,id,shortUrl"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        cards = response.json()
        if not cards:
            return "Nenhum card encontrado na lista TO-DO."
        lines = [f"Encontrei {len(cards)} card(s) na lista TO-DO:\n"]
        for i, card in enumerate(cards, 1):
            lines.append(f"{i}. [{card['id']}] {card['name']}")
            if card.get("desc"):
                lines.append(f"   Descrição: {card['desc']}")
            lines.append(f"   URL: {card['shortUrl']}")
        return "\n".join(lines)


def move_card_to_list(
    card_id: str,
    target_list_id: str,
    api_key: str | None = None,
    token: str | None = None,
) -> None:
    """Move card para outra lista no Trello. Lanca HTTPError em caso de falha."""
    _key   = api_key or os.environ["TRELLO_API_KEY"]
    _token = token   or os.environ["TRELLO_TOKEN"]
    resp = requests.put(
        f"https://api.trello.com/1/cards/{card_id}",
        params={"key": _key, "token": _token, "idList": target_list_id},
        timeout=10,
    )
    resp.raise_for_status()


def update_card_description(
    card_id: str,
    description: str,
    api_key: str | None = None,
    token: str | None = None,
) -> None:
    """Atualiza descricao de um card no Trello. Lanca HTTPError em caso de falha."""
    _key   = api_key or os.environ["TRELLO_API_KEY"]
    _token = token   or os.environ["TRELLO_TOKEN"]
    resp = requests.put(
        f"https://api.trello.com/1/cards/{card_id}",
        params={"key": _key, "token": _token, "desc": description},
        timeout=10,
    )
    resp.raise_for_status()
