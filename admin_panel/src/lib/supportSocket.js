function apiBase() {
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
}

let socket = null;
let stopped = true;
let retryTimer = null;
let attempt = 0;
let handlers = {};

function socketUrl(token) {
  const stripped = apiBase().replace(/\/api\/v1\/?$/, '');
  const absolute = /^https?:\/\//.test(stripped)
    ? stripped
    : `${window.location.origin}${stripped}`;
  const ws = absolute.replace(/\/$/, '').replace(/^http/, 'ws');
  return `${ws}/ws/support/?audience=staff&token=${encodeURIComponent(token)}`;
}

async function refreshedToken() {
  const refresh = localStorage.getItem('admin_refresh_token');
  if (!refresh) return null;
  const response = await fetch(`${apiBase()}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) return null;
  const body = await response.json();
  if (body.access) localStorage.setItem('admin_access_token', body.access);
  return body.access || null;
}

function scheduleRetry() {
  if (stopped) return;
  const delay = Math.min(30000, 1000 * (2 ** Math.min(attempt, 5)));
  attempt += 1;
  clearTimeout(retryTimer);
  retryTimer = setTimeout(connect, delay);
}

function connect() {
  if (stopped) return;
  const token = localStorage.getItem('admin_access_token');
  if (!token) return;
  if (socket) {
    socket.onclose = null;
    socket.close();
  }
  const current = new WebSocket(socketUrl(token));
  socket = current;
  current.onopen = () => {
    attempt = 0;
  };
  current.onmessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.type === 'message.created' && message.message) handlers.onMessage?.(message.message);
    if (message.type === 'message.read') handlers.onRead?.(message);
    if (message.type === 'presence') handlers.onPresence?.(Boolean(message.agent_online));
    if (message.type === 'typing') handlers.onTyping?.(message);
  };
  current.onclose = (event) => {
    if (stopped || socket !== current) return;
    if (event.code === 4401) {
      refreshedToken().then((next) => (next ? connect() : stopSupportSocket())).catch(scheduleRetry);
      return;
    }
    scheduleRetry();
  };
}

export function sendSupportTyping(conversationId, active) {
  if (!socket || socket.readyState !== WebSocket.OPEN || !conversationId) return;
  socket.send(JSON.stringify({ type: 'typing', conversation_id: conversationId, active }));
}

export function startSupportSocket(nextHandlers) {
  handlers = nextHandlers || {};
  stopped = false;
  connect();
}

export function stopSupportSocket() {
  stopped = true;
  clearTimeout(retryTimer);
  handlers = {};
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
}
