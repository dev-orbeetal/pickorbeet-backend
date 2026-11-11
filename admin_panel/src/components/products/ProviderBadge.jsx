const LABELS = {
  itech: 'i-Tech',
  marvellous: 'Marvellous',
};

export function providerLabel(provider) {
  if (!provider) return '';
  return LABELS[provider] || provider;
}

export default function ProviderBadge({ provider }) {
  const label = providerLabel(provider);
  if (!label) return null;
  return (
    <span className="px-1.5 py-0.5 bg-sky-50 text-sky-700 rounded text-[10px] font-bold uppercase">
      {label}
    </span>
  );
}
