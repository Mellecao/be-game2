// workers/shared/trello.ts
const BASE = 'https://api.trello.com/1';
function auth() {
  const key = process.env.TRELLO_API_KEY;
  const token = process.env.TRELLO_TOKEN;
  if (!key || !token) throw new Error('TRELLO_API_KEY and TRELLO_TOKEN required');
  return { key, token };
}
export async function listCards(listId: string) {
  const { key, token } = auth();
  const res = await fetch(`${BASE}/lists/${listId}/cards?key=${key}&token=${token}&fields=name,desc,id`);
  if (!res.ok) throw new Error(`Trello ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }[]>;
}
export async function getCard(cardId: string) {
  const { key, token } = auth();
  const res = await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}&fields=name,desc`);
  if (!res.ok) throw new Error(`Trello ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }>;
}
export async function moveCard(cardId: string, listId: string) {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idList: listId }),
  });
}
