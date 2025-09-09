// Services and Events module

export const EVENTS = {
    ITEM_PICKED: 'item_picked',
    DIALOGUE_START: 'dialogue_start',
    DIALOGUE_END: 'dialogue_end',
    PLAYER_HIT: 'player_hit'
};

class EventBusClass extends Phaser.Events.EventEmitter {}
export const EventBus = new EventBusClass();

export class ApiClient {
    static async getJson(url, options = {}) {
        const resp = await fetch(url, { ...options });
        if (!resp.ok) throw new Error(`GET ${url} failed: ${resp.status}`);
        return resp.json();
    }

    static async postJson(url, body, options = {}) {
        const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, body: JSON.stringify(body), ...options });
        if (!resp.ok) throw new Error(`POST ${url} failed: ${resp.status}`);
        return resp.json();
    }
}


