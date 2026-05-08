// workers/shared/llm.ts
import Anthropic from '@anthropic-ai/sdk';

let _client: Anthropic | null = null;

export function getLLM(): Anthropic {
  if (!_client) {
    _client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return _client;
}

export async function ask(system: string, userMessage: string, maxTokens = 2048): Promise<string> {
  const client = getLLM();
  const msg = await client.messages.create({
    model:      process.env.AGENT_MODEL ?? 'claude-sonnet-4-6',
    max_tokens: maxTokens,
    system,
    messages:   [{ role: 'user', content: userMessage }],
  });
  const block = msg.content[0];
  return block.type === 'text' ? block.text : '';
}
