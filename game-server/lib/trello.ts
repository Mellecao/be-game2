const BASE = 'https://api.trello.com/1';

function auth() {
  const key   = process.env.TRELLO_API_KEY;
  const token = process.env.TRELLO_TOKEN;
  if (!key || !token) throw new Error('TRELLO_API_KEY and TRELLO_TOKEN are required');
  return { key, token };
}

export async function listCards(listId: string): Promise<{ id: string; name: string; desc: string }[]> {
  const { key, token } = auth();
  const url = `${BASE}/lists/${listId}/cards?key=${key}&token=${token}&fields=name,desc,id`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Trello error ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }[]>;
}

export async function getCard(cardId: string): Promise<{ id: string; name: string; desc: string }> {
  const { key, token } = auth();
  const url = `${BASE}/cards/${cardId}?key=${key}&token=${token}&fields=name,desc`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Trello error ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }>;
}

export async function moveCard(cardId: string, listId: string): Promise<void> {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idList: listId }),
  });
}

export async function updateCardDesc(cardId: string, desc: string): Promise<void> {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ desc }),
  });
}
