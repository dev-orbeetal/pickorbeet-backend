const listeners = new Set();
const presented = new Set();

let state = { items: [], unreadCount: 0, loading: false };
let socket = null;
let stopped = true;
let retryTimer = null;
let attempt = 0;

function apiBase() {
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
}

export function getNotificationState() {
  return state;
}

export function subscribeNotifications(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function publish(next) {
  state = next;
  listeners.forEach((listener) => listener());
}

async function authorized(path, options = {}) {
  const token = localStorage.getItem('admin_access_token');
  const response = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status !== 401) return response;
  const refresh = localStorage.getItem('admin_refresh_token');
  if (!refresh) return response;
  const renewed = await fetch(`${apiBase()}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!renewed.ok) return response;
  const body = await renewed.json();
  if (body.access) localStorage.setItem('admin_access_token', body.access);
  return fetch(`${apiBase()}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${body.access}`,
      ...(options.headers || {}),
    },
  });
}

function timeLabel(created) {
  const value = new Date(created);
  if (Number.isNaN(value.getTime())) return '';
  return value.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export async function loadNotifications() {
  publish({ ...state, loading: true });
  try {
    const [listResponse, countResponse] = await Promise.all([
      authorized('/notifications/'),
      authorized('/notifications/unread-count/'),
    ]);
    const list = listResponse.ok ? await listResponse.json() : { results: [] };
    const count = countResponse.ok ? await countResponse.json() : { unread_count: 0 };
    const items = (list.results || []).map((row) => ({
      id: row.id,
      title: row.title,
      body: row.body,
      time: timeLabel(row.created_at),
      unread: !row.read_at,
      orderId: row.data?.order_id || '',
    }));
    publish({ items, unreadCount: count.unread_count || 0, loading: false });
  } catch {
    publish({ ...state, loading: false });
  }
}

export async function markNotificationRead(id) {
  const items = state.items.map((item) => (item.id === id ? { ...item, unread: false } : item));
  const wasUnread = state.items.some((item) => item.id === id && item.unread);
  publish({ ...state, items, unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount });
  await authorized(`/notifications/${id}/read/`, { method: 'POST' });
}

function upsert(row, unreadCount) {
  const item = {
    id: row.id,
    title: row.title,
    body: row.body,
    time: timeLabel(row.created_at),
    unread: !row.read_at,
    orderId: row.data?.order_id || '',
  };
  publish({
    items: [item, ...state.items.filter((existing) => existing.id !== item.id)].slice(0, 20),
    unreadCount,
    loading: false,
  });
  if (!presented.has(item.id)) presented.add(item.id);
}

function socketUrl(token) {
  const stripped = apiBase().replace(/\/api\/v1\/?$/, '');
  const absolute = /^https?:\/\//.test(stripped)
    ? stripped
    : `${window.location.origin}${stripped}`;
  const ws = absolute.replace(/\/$/, '').replace(/^http/, 'ws');
  return `${ws}/ws/notifications/?token=${encodeURIComponent(token)}`;
}

function scheduleRetry() {
  if (stopped) return;
  const delay = Math.min(30000, 1000 * (2 ** Math.min(attempt, 5)));
  attempt += 1;
  clearTimeout(retryTimer);
  retryTimer = setTimeout(connect, delay);
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
    if (message.type === 'notification.read') {
      publish({ ...state, unreadCount: message.unread_count || 0 });
      return;
    }
    if (message.type === 'notification.created' && message.notification) {
      upsert(message.notification, message.unread_count || 0);
    }
  };
  current.onclose = (event) => {
    if (stopped || socket !== current) return;
    if (event.code === 4401) {
      refreshedToken().then((next) => (next ? connect() : stopNotificationSocket())).catch(scheduleRetry);
      return;
    }
    scheduleRetry();
  };
}

export function startNotificationSocket() {
  stopped = false;
  loadNotifications();
  connect();
}

export function stopNotificationSocket() {
  stopped = true;
  clearTimeout(retryTimer);
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
  publish({ items: [], unreadCount: 0, loading: false });
}
