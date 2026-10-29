const PRESETS = [
  { id: 'today', label: 'Today', days: 0 },
  { id: '7d', label: '7 days', days: 6 },
  { id: '30d', label: '30 days', days: 29 },
  { id: '90d', label: '90 days', days: 89 },
];

const BD_DIVISIONS = {
  A: 'Barishal',
  B: 'Chattogram',
  C: 'Dhaka',
  D: 'Khulna',
  E: 'Rajshahi',
  F: 'Rangpur',
  G: 'Sylhet',
  H: 'Mymensingh',
};

const SOURCE_LABELS = {
  direct: 'Direct',
  search: 'Search',
  whatsapp: 'WhatsApp',
  facebook: 'Facebook',
  instagram: 'Instagram',
  other: 'Other',
};

const DEVICE_LABELS = {
  mobile: 'Mobile',
  tablet: 'Tablet',
  desktop: 'Desktop',
};

export { PRESETS, SOURCE_LABELS, DEVICE_LABELS };

export function dhakaToday(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Dhaka',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

function shiftDate(iso, days) {
  const [year, month, day] = iso.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function isDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export function resolveRange(query) {
  const today = dhakaToday();
  if (query?.range === 'custom' && isDate(query.from) && isDate(query.to)) {
    const from = query.from <= query.to ? query.from : query.to;
    const to = query.from <= query.to ? query.to : query.from;
    return { from, to, preset: 'custom' };
  }
  const preset = PRESETS.find((item) => item.id === query?.range) || PRESETS[1];
  return {
    from: preset.days === 0 ? today : shiftDate(today, -preset.days),
    to: today,
    preset: preset.id,
  };
}

export function formatChange(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  const rounded = Math.round(Number(value) * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${rounded > 0 ? '+' : ''}${text}%`;
}

export function formatDuration(ms) {
  const seconds = Math.round((Number(ms) || 0) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  if (minutes < 60) return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const extra = minutes % 60;
  return extra ? `${hours}h ${extra}m` : `${hours}h`;
}

export function formatWhen(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Dhaka',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function timeAgo(iso) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return formatWhen(iso);
}

export function shortDate(iso) {
  if (!iso) return '';
  const [year, month, day] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

let regionNames;

export function countryName(code) {
  if (!code || code === 'Unknown') return 'Unknown';
  try {
    regionNames = regionNames || new Intl.DisplayNames(['en'], { type: 'region' });
    return regionNames.of(code) || code;
  } catch {
    return code;
  }
}

export function dimensionLabel(dimension, label) {
  if (!label || label === 'Unknown') return 'Unknown';
  if (dimension === 'country') return countryName(label);
  if (dimension === 'region' && BD_DIVISIONS[label]) return BD_DIVISIONS[label];
  if (dimension === 'device') return DEVICE_LABELS[label] || label;
  if (dimension === 'source') return SOURCE_LABELS[label] || label;
  return label;
}

export function number(value) {
  return (Number(value) || 0).toLocaleString();
}
