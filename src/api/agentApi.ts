export interface ChatResponse {
  response: string;
  npc_id: string;
}

export async function sendChat(
  npcId: string,
  message: string
): Promise<ChatResponse> {
  const startedAt = performance.now();
  console.log(`[chat] enviando mensagem para ${npcId}:`, message);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ npc_id: npcId, message }),
    });

    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);

    if (!res.ok) {
      const text = await res.text();
      console.error(`[chat] HTTP ${res.status} apos ${elapsed}s:`, text);
      throw new Error(`API retornou ${res.status}: ${text.slice(0, 200)}`);
    }

    const data = await res.json();
    console.log(`[chat] resposta recebida em ${elapsed}s (${data.response?.length ?? 0} chars)`);
    return data;
  } catch (err) {
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    console.error(`[chat] falhou apos ${elapsed}s:`, err);
    if (err instanceof TypeError) {
      throw new Error(
        `Conexao falhou apos ${elapsed}s. Verifique se o backend esta rodando (python -m uvicorn server.api:app --port 8000) e o Ollama esta ativo.`
      );
    }
    throw err;
  }
}
