/**
 * EventEmitter simple compatible con React Native
 * Alternativa a Node.js EventEmitter para comunicación interna
 */
export class EventEmitter {
  private events: Map<string, Array<(data: any) => void>> = new Map();

  on(event: string, callback: (data: any) => void) {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event)!.push(callback);
  }

  off(event: string, callback: (data: any) => void) {
    if (!this.events.has(event)) {
      return;
    }

    const callbacks = this.events.get(event)!;
    const index = callbacks.indexOf(callback);

    if (index > -1) {
      callbacks.splice(index, 1);
    }

    if (callbacks.length === 0) {
      this.events.delete(event);
    }
  }

  emit(event: string, data: any) {
    if (!this.events.has(event)) {
      return;
    }

    const callbacks = this.events.get(event)!;
    callbacks.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in event callback for "${event}":`, error);
      }
    });
  }

  removeAllListeners(event?: string) {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
  }
}
