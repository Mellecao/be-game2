import { EventEmitter } from 'node:events';

export const bus = new EventEmitter();
bus.setMaxListeners(100);

export function emit(type: string, data: unknown): void {
  bus.emit('event', JSON.stringify({ type, data }));
}
