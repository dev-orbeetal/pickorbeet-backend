import { Plus, Trash2 } from 'lucide-react';

export function cleanSpecifications(rows) {
  const specifications = [];
  for (const row of rows) {
    const name = (row.name || '').trim();
    const value = (row.value || '').trim();
    if (!name && !value) continue;
    if (!name || !value) {
      return { error: 'Each specification needs a name and a value.' };
    }
    specifications.push({ name, value });
  }
  return { specifications };
}

export default function SpecificationFields({ rows, onChange }) {
  const update = (index, key, value) => {
    onChange(rows.map((row, rowIndex) => (
      rowIndex === index ? { ...row, [key]: value } : row
    )));
  };

  return (
    <div className="card">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Specifications</h2>
          <p className="mt-1 text-sm text-gray-500">
            These rows appear in the product page table. Brand, model, and warranty are typical.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange([...rows, { name: '', value: '' }])}
          className="btn btn-secondary text-sm"
        >
          <Plus className="mr-1 h-4 w-4" />
          Add row
        </button>
      </div>

      {rows.length === 0 && (
        <p className="text-sm text-gray-500">No specification rows yet.</p>
      )}

      <div className="space-y-3">
        {rows.map((row, index) => (
          <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-3">
            <input
              type="text"
              value={row.name}
              onChange={(event) => update(index, 'name', event.target.value)}
              className="input"
              placeholder="Name"
              maxLength={80}
              aria-label={`Specification ${index + 1} name`}
            />
            <input
              type="text"
              value={row.value}
              onChange={(event) => update(index, 'value', event.target.value)}
              className="input"
              placeholder="Value"
              maxLength={255}
              aria-label={`Specification ${index + 1} value`}
            />
            <button
              type="button"
              onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))}
              className="rounded-lg p-2 text-gray-500 hover:bg-red-50 hover:text-red-600"
              aria-label={`Remove specification ${index + 1}`}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
