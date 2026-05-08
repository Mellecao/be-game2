export interface PipelineTask {
  id: string;
  card_name: string;
  status: string;
  log: string;
  created_at: number;
  start_at: number;
  step: number;
  remaining_seconds: number;
}

const _tasks = new Map<string, PipelineTask>();

export function getTasks(): PipelineTask[] {
  const now = Date.now() / 1000;
  return [..._tasks.values()]
    .map((t) => ({
      ...t,
      remaining_seconds: t.status === 'waiting' ? Math.max(0, Math.floor(t.start_at - now)) : 0,
    }))
    .sort((a, b) => b.created_at - a.created_at);
}

export function upsertTask(task: Partial<PipelineTask> & { id: string; card_name: string }): void {
  const now = Date.now() / 1000;
  const existing = _tasks.get(task.id);
  _tasks.set(task.id, {
    status: 'waiting', log: '', step: 0,
    created_at: now, start_at: now + 180, remaining_seconds: 180,
    ...existing,
    ...task,
  } as PipelineTask);
}

export function cancelTask(taskId: string): boolean {
  const task = _tasks.get(taskId);
  if (!task) return false;
  if (['done', 'error', 'cancelled'].includes(task.status)) return false;
  task.status = 'cancelled';
  task.log    = 'Cancelado pelo usuario';
  return true;
}
