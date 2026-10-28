import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Plus, Printer, RefreshCw, Trash2, X } from 'lucide-react';

const PRESETS = [
  { name: 'Black', hex: '#171717' },
  { name: 'White', hex: '#F7F7F7' },
  { name: 'Red', hex: '#E11D48' },
  { name: 'Blue', hex: '#3B82F6' },
  { name: 'Green', hex: '#16A34A' },
  { name: 'Yellow', hex: '#F5C518' },
  { name: 'Orange', hex: '#FF7A1A' },
  { name: 'Purple', hex: '#7C3AED' },
  { name: 'Pink', hex: '#EC4899' },
  { name: 'Brown', hex: '#8B5E3C' },
  { name: 'Gray', hex: '#9CA3AF' },
  { name: 'Navy', hex: '#1E3A8A' },
  { name: 'Beige', hex: '#E7D7C5' },
  { name: 'Maroon', hex: '#7F1D1D' },
  { name: 'Olive', hex: '#6B7C3A' },
  { name: 'Silver', hex: '#C5CDD8' },
];

let keySequence = 0;
function nextKey() {
  keySequence += 1;
  return `opt-${keySequence}`;
}

function skuToken(label) {
  const cleaned = String(label || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  return cleaned.slice(0, 8) || 'X';
}

function previewSku(productSku, labels) {
  const base = String(productSku || 'ITEM').replace(/[^A-Za-z0-9-]/g, '').toUpperCase().slice(0, 20) || 'ITEM';
  return [base, ...labels.map(skuToken)].join('-').slice(0, 50);
}

function sameSelection(left, right) {
  if (left.length !== right.length) return false;
  return left.every((item) => right.some((other) => other.name === item.name && other.label === item.label));
}

function isSubset(part, whole) {
  return part.every((item) => whole.some((other) => other.name === item.name && other.label === item.label));
}

function assignSkus(productSku, rows) {
  const taken = new Set(rows.filter((row) => row.id && row.sku).map((row) => row.sku));
  return rows.map((row) => {
    if (row.id && row.sku) return row;
    const labels = row.selections.map((item) => item.label);
    let sku = previewSku(productSku, labels);
    let number = 2;
    while (taken.has(sku)) {
      const suffix = `-${number}`;
      sku = `${previewSku(productSku, labels).slice(0, 50 - suffix.length)}${suffix}`;
      number += 1;
    }
    taken.add(sku);
    return { ...row, sku };
  });
}

function combinations(groups) {
  let rows = [[]];
  groups.forEach((group) => {
    const next = [];
    rows.forEach((row) => {
      group.values.forEach((value) => {
        next.push([...row, { name: group.name.trim(), label: value.label }]);
      });
    });
    rows = next;
  });
  return rows;
}

function reconcile(groups, rows, productSku, prefix) {
  const named = groups.filter((group) => group.name.trim());
  if (!named.length || named.some((group) => group.values.length === 0)) return [];
  const combos = combinations(named);
  const next = combos.map((selections, index) => {
    const exact = rows.find((row) => sameSelection(row.selections, selections));
    const parent = exact || rows.find((row) => {
      if (!row.selections.length || !isSubset(row.selections, selections)) return false;
      const extensions = combos.filter((candidate) => isSubset(row.selections, candidate));
      return extensions.length === 1;
    });
    if (parent) return { ...parent, selections };
    return {
      key: nextKey(),
      id: null,
      sku: '',
      barcode: newBarcode(prefix, index),
      price: '',
      stock: 0,
      lowStock: 10,
      isActive: true,
      selections,
    };
  });
  return assignSkus(productSku, next);
}

function newBarcode(prefix, index) {
  const stamp = Date.now().toString().slice(-8);
  const salt = Math.floor(Math.random() * 90 + 10);
  return `${prefix || 'ZZ'}V-${stamp}${String(index).padStart(2, '0')}${salt}`;
}

function presetHex(label) {
  const match = PRESETS.find((preset) => preset.name.toLowerCase() === String(label || '').trim().toLowerCase());
  return match?.hex || '#D5DDE8';
}

function groupState(group) {
  return {
    key: nextKey(),
    name: group.name || '',
    kind: group.kind === 'swatch' ? 'swatch' : 'text',
    draft: '',
    draftHex: '#3B82F6',
    values: (group.values || []).map((value) => ({
      key: nextKey(),
      label: value.label || '',
      colorHex: value.colorHex || value.color_hex || presetHex(value.label),
    })),
  };
}

function groupsFromProduct(optionGroups, variants) {
  if (optionGroups?.length) return optionGroups.map(groupState);
  const sizes = [];
  const colors = [];
  (variants || []).forEach((variant) => {
    if (variant.size && !sizes.includes(variant.size)) sizes.push(variant.size);
    if (variant.color && !colors.includes(variant.color)) colors.push(variant.color);
  });
  const groups = [];
  if (sizes.length) {
    groups.push(groupState({
      name: 'Size',
      kind: 'text',
      values: sizes.map((label) => ({ label })),
    }));
  }
  if (colors.length) {
    groups.push(groupState({
      name: 'Color',
      kind: 'swatch',
      values: colors.map((label) => ({ label, colorHex: presetHex(label) })),
    }));
  }
  return groups;
}

function rowSelections(variant) {
  if (variant.options?.length) {
    return variant.options.map((option) => ({ name: option.name, label: option.label }));
  }
  const selections = [];
  if (variant.size) selections.push({ name: 'Size', label: variant.size });
  if (variant.color) selections.push({ name: 'Color', label: variant.color });
  return selections;
}

function rowsFromProduct(variants) {
  return (variants || []).filter((variant) => rowSelections(variant).length).map((variant) => ({
    key: variant.id || nextKey(),
    id: variant.id || null,
    sku: variant.sku || '',
    barcode: variant.barcode || '',
    price: variant.price ?? '',
    stock: variant.stock_quantity ?? 0,
    lowStock: variant.low_stock_threshold ?? 10,
    isActive: variant.is_active !== false,
    selections: rowSelections(variant),
  }));
}

const VariantOptions = forwardRef(function VariantOptions({
  productSku,
  barcodePrefix,
  productName,
  productPrice,
  initialGroups,
  initialVariants,
  onCount,
}, ref) {
  const [groups, setGroups] = useState(() => groupsFromProduct(initialGroups, initialVariants));
  const [rows, setRows] = useState(() => rowsFromProduct(initialVariants));
  const onCountRef = useRef(onCount);
  onCountRef.current = onCount;

  useEffect(() => {
    onCountRef.current?.(rows.length);
  }, [rows.length]);

  useEffect(() => {
    setRows((current) => assignSkus(productSku, current));
  }, [productSku]);

  const changeGroups = (next) => {
    setGroups(next);
    setRows((current) => reconcile(next, current, productSku, barcodePrefix));
  };

  const patchGroup = (key, patch) => {
    setGroups((current) => current.map((group) => (group.key === key ? { ...group, ...patch } : group)));
    if (!Object.prototype.hasOwnProperty.call(patch, 'name')) return;
    const previous = groups.find((group) => group.key === key)?.name.trim();
    const renamed = patch.name.trim();
    if (!previous || previous === renamed) return;
    setRows((current) => current.map((row) => ({
      ...row,
      selections: row.selections.map((item) => (item.name === previous ? { ...item, name: renamed } : item)),
    })));
  };

  useImperativeHandle(ref, () => ({
    getSetup() {
      const named = groups.filter((group) => group.name.trim() || group.values.length);
      if (!named.length) return { payload: { option_groups: [], variants: [] } };
      const names = named.map((group) => group.name.trim().toLowerCase());
      if (named.some((group) => !group.name.trim())) return { error: 'Name each option.' };
      if (new Set(names).size !== names.length) return { error: 'Option names must be different.' };
      const missing = named.find((group) => group.values.length === 0);
      if (missing) return { error: `Add a value for ${missing.name.trim()}.` };
      return {
        payload: {
          option_groups: named.map((group) => ({
            name: group.name.trim(),
            kind: group.kind,
            values: group.values.map((value) => ({
              label: value.label,
              color_hex: group.kind === 'swatch' ? value.colorHex : '',
            })),
          })),
          variants: rows.map((row) => ({
            id: row.id,
            barcode: row.barcode,
            price: row.price === '' || row.price === null ? null : row.price,
            stock_quantity: Number(row.stock) || 0,
            low_stock_threshold: Number(row.lowStock) || 0,
            is_active: row.isActive,
            selections: row.selections,
          })),
        },
      };
    },
  }), [barcodePrefix, groups, productSku, rows]);

  const addGroup = () => {
    changeGroups([...groups, {
      key: nextKey(),
      name: '',
      kind: 'text',
      draft: '',
      draftHex: '#3B82F6',
      values: [],
    }]);
  };

  const addValue = (group) => {
    const label = group.draft.trim();
    if (!label) return;
    if (group.values.some((value) => value.label.toLowerCase() === label.toLowerCase())) return;
    const colorHex = group.kind === 'swatch' ? normalizeHex(group.draftHex) : '';
    if (group.kind === 'swatch' && !colorHex) return;
    changeGroups(groups.map((item) => (item.key === group.key ? {
      ...item,
      draft: '',
      values: [...item.values, { key: nextKey(), label, colorHex: colorHex || '#D5DDE8' }],
    } : item)));
  };

  const printBarcode = (row) => {
    const label = [productName, ...row.selections.map((item) => item.label)].filter(Boolean).join(' - ');
    const price = row.price || productPrice || '';
    const popup = window.open('', '_blank');
    if (!popup) return;
    const safeLabel = label.replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
    const safeSku = String(row.sku || '').replace(/[&<>"]/g, '');
    const safeCode = String(row.barcode || '').replace(/[^A-Za-z0-9-]/g, '');
    popup.document.write(`<!DOCTYPE html><html><head><title>Variant barcode</title>
      <style>body{font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
      .bc{text-align:center;padding:20px}.name{font-size:16px;font-weight:700}.price{font-size:20px;font-weight:700;color:#059669;margin-top:8px}
      .sku{font-size:11px;color:#666;margin-top:4px}</style></head>
      <body><div class="bc"><div class="name">${safeLabel}</div><svg id="bc"></svg>
      ${price ? `<div class="price">৳${price}</div>` : ''}
      ${safeSku ? `<div class="sku">SKU: ${safeSku}</div>` : ''}
      </div><script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
      <script>JsBarcode("#bc","${safeCode}",{format:"CODE128",width:2,height:80,displayValue:true,fontSize:14,margin:10});
      setTimeout(()=>window.print(),500)</script></body></html>`);
    popup.document.close();
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between gap-3 mb-1">
        <h2 className="text-lg font-semibold">Variants</h2>
        <button type="button" onClick={addGroup} className="btn btn-secondary text-sm">
          <Plus className="w-4 h-4 mr-1" />
          Add option
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Name an option such as Size, Color, or Storage, then add its values. Each combination gets a SKU.
      </p>

      {groups.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No options yet. Add one when this product comes in more than one version.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.key} className="rounded-lg border border-gray-200 p-4">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto]">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Option</label>
                  <input
                    value={group.name}
                    onChange={(event) => patchGroup(group.key, { name: event.target.value })}
                    className="input text-sm"
                    placeholder="Size, Color, Storage"
                    maxLength={40}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Shown as</label>
                  <select
                    value={group.kind}
                    onChange={(event) => patchGroup(group.key, {
                      kind: event.target.value,
                      values: group.values.map((value) => ({
                        ...value,
                        colorHex: value.colorHex || '#D5DDE8',
                      })),
                    })}
                    className="input text-sm"
                  >
                    <option value="text">Text</option>
                    <option value="swatch">Color swatch</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    type="button"
                    onClick={() => changeGroups(groups.filter((item) => item.key !== group.key))}
                    className="btn btn-secondary text-sm text-red-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {group.values.map((value) => (
                  <span key={value.key} className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2 py-1 text-sm">
                    {group.kind === 'swatch' && (
                      <label className="relative h-5 w-5 overflow-hidden rounded-full border border-gray-200" style={{ background: value.colorHex }}>
                        <span className="sr-only">Color for {value.label}</span>
                        <input
                          type="color"
                          value={toColorInput(value.colorHex)}
                          onChange={(event) => patchGroup(group.key, {
                            values: group.values.map((item) => (
                              item.key === value.key ? { ...item, colorHex: event.target.value.toUpperCase() } : item
                            )),
                          })}
                          className="absolute inset-0 cursor-pointer opacity-0"
                        />
                      </label>
                    )}
                    {value.label}
                    <button
                      type="button"
                      aria-label={`Remove ${value.label}`}
                      onClick={() => changeGroups(groups.map((item) => (item.key === group.key ? {
                        ...item,
                        values: item.values.filter((entry) => entry.key !== value.key),
                      } : item)))}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  value={group.draft}
                  onChange={(event) => patchGroup(group.key, { draft: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addValue(group);
                    }
                  }}
                  className="input text-sm w-40"
                  placeholder={group.kind === 'swatch' ? 'Midnight' : 'M'}
                  maxLength={40}
                />
                {group.kind === 'swatch' && (
                  <>
                    <label className="relative h-10 w-10 overflow-hidden rounded-full border border-gray-200 shadow-sm" style={{ background: toColorInput(group.draftHex) }}>
                      <span className="sr-only">Pick a color</span>
                      <input
                        type="color"
                        value={toColorInput(group.draftHex)}
                        onChange={(event) => patchGroup(group.key, { draftHex: event.target.value.toUpperCase() })}
                        className="absolute inset-0 cursor-pointer opacity-0"
                      />
                    </label>
                    <input
                      value={group.draftHex}
                      onChange={(event) => patchGroup(group.key, { draftHex: event.target.value })}
                      className="input text-sm w-28 font-mono"
                      placeholder="#0B1F3A"
                      maxLength={7}
                    />
                  </>
                )}
                <button type="button" onClick={() => addValue(group)} className="btn btn-secondary text-sm">
                  Add value
                </button>
              </div>
              {group.kind === 'swatch' && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {PRESETS.map((preset) => (
                    <button
                      key={preset.hex}
                      type="button"
                      title={preset.name}
                      onClick={() => patchGroup(group.key, {
                        draftHex: preset.hex,
                        draft: group.draft.trim() ? group.draft : preset.name,
                      })}
                      className="h-6 w-6 rounded-full border border-black/10"
                      style={{ background: preset.hex }}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {rows.length > 0 && (
        <div className="mt-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-800">Combinations</h3>
          {rows.map((row) => (
            <div key={row.key} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-gray-800">
                  {row.selections.map((item) => item.label).join(' / ')}
                </p>
                <p className="font-mono text-xs text-gray-500">SKU {row.sku}</p>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <label className="block text-xs font-medium text-gray-600">
                  Price (৳)
                  <input
                    type="number"
                    value={row.price}
                    min="0"
                    step="0.01"
                    placeholder="Same as product"
                    onChange={(event) => setRows(rows.map((item) => (
                      item.key === row.key ? { ...item, price: event.target.value } : item
                    )))}
                    className="input mt-1 text-sm"
                  />
                </label>
                <label className="block text-xs font-medium text-gray-600">
                  Stock
                  <input
                    type="number"
                    value={row.stock}
                    min="0"
                    onChange={(event) => setRows(rows.map((item) => (
                      item.key === row.key ? { ...item, stock: event.target.value } : item
                    )))}
                    className="input mt-1 text-sm"
                  />
                </label>
                <label className="block text-xs font-medium text-gray-600">
                  Low stock alert
                  <input
                    type="number"
                    value={row.lowStock}
                    min="0"
                    onChange={(event) => setRows(rows.map((item) => (
                      item.key === row.key ? { ...item, lowStock: event.target.value } : item
                    )))}
                    className="input mt-1 text-sm"
                  />
                </label>
                <label className="block text-xs font-medium text-gray-600">
                  Barcode
                  <div className="mt-1 flex gap-2">
                    <input value={row.barcode} readOnly className="input text-sm font-mono" />
                    <button
                      type="button"
                      title="Regenerate barcode"
                      onClick={() => setRows(rows.map((item) => (
                        item.key === row.key ? { ...item, barcode: newBarcode(barcodePrefix, 0) } : item
                      )))}
                      className="btn btn-secondary px-2"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    {row.barcode && (
                      <button type="button" title="Print barcode" onClick={() => printBarcode(row)} className="btn btn-secondary px-2">
                        <Printer className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

function normalizeHex(value) {
  const hex = String(value || '').trim();
  return /^#[0-9A-Fa-f]{6}$/.test(hex) ? hex.toUpperCase() : '';
}

function toColorInput(value) {
  return normalizeHex(value) || '#3B82F6';
}

export default VariantOptions;
