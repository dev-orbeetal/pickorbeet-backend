import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Search, X } from 'lucide-react';

const PANEL_GAP = 4;
const VIEWPORT_MARGIN = 8;
const PANEL_MIN_WIDTH = 320;
const PANEL_MAX_HEIGHT = 300;

function panelPlacement(trigger) {
  const rect = trigger.getBoundingClientRect();
  const { innerWidth, innerHeight } = window;
  const width = Math.min(Math.max(rect.width, PANEL_MIN_WIDTH), innerWidth - VIEWPORT_MARGIN * 2);
  const spaceBelow = innerHeight - rect.bottom - PANEL_GAP - VIEWPORT_MARGIN;
  const spaceAbove = rect.top - PANEL_GAP - VIEWPORT_MARGIN;
  const above = spaceBelow < PANEL_MAX_HEIGHT && spaceAbove > spaceBelow;
  return {
    left: Math.max(VIEWPORT_MARGIN, Math.min(rect.left, innerWidth - width - VIEWPORT_MARGIN)),
    width,
    maxHeight: Math.min(PANEL_MAX_HEIGHT, above ? spaceAbove : spaceBelow),
    ...(above ? { bottom: innerHeight - rect.top + PANEL_GAP } : { top: rect.bottom + PANEL_GAP }),
  };
}

/**
 * Compact searchable dropdown for dense forms (e.g. purchase lines).
 * options: [{ value, label, keywords? }]
 * The panel renders in a portal so scrolling tables and modals cannot clip it.
 */
export default function SearchableSelect({
  options = [],
  value = '',
  onChange,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  required = false,
  disabled = false,
  emptyLabel = 'No matches',
  className = '',
}) {
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const searchRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState(null);
  const [query, setQuery] = useState('');

  const selected = useMemo(
    () => options.find((option) => String(option.value) === String(value)) || null,
    [options, value],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((option) => {
      const hay = `${option.label || ''} ${option.keywords || ''}`.toLowerCase();
      return hay.includes(q);
    });
  }, [options, query]);

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0);
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target) && !panelRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    const onResize = () => setPlacement(panelPlacement(triggerRef.current));
    const onScroll = (event) => {
      if (!panelRef.current?.contains(event.target)) onResize();
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const toggle = () => {
    if (disabled) return;
    setPlacement(panelPlacement(triggerRef.current));
    setOpen((current) => !current);
  };

  const pick = (next) => {
    onChange?.(next);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={toggle}
        className={`input flex w-full items-center justify-between gap-2 text-left ${
          disabled ? 'cursor-not-allowed opacity-60' : ''
        } ${!selected ? 'text-gray-400' : 'text-gray-900'}`}
      >
        <span className="min-w-0 truncate">
          {selected?.label || placeholder}
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Keep native required validation without showing the native select. */}
      {required ? (
        <select
          className="sr-only"
          tabIndex={-1}
          required
          value={value || ''}
          onChange={() => {}}
          aria-hidden="true"
        >
          <option value="">Select</option>
          {options.map((option) => (
            <option key={String(option.value)} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : null}

      {open && createPortal(
        <div
          ref={panelRef}
          style={placement}
          className="fixed z-[90] flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg"
        >
          <div className="shrink-0 border-b border-gray-100 p-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={searchPlaceholder}
                className="w-full rounded-md border border-gray-200 py-2 pl-8 pr-8 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  aria-label="Clear search"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </div>
          </div>
          <ul role="listbox" className="min-h-0 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2.5 text-sm text-gray-500">{emptyLabel}</li>
            ) : (
              filtered.map((option) => {
                const active = String(option.value) === String(value);
                return (
                  <li key={String(option.value)}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      onClick={() => pick(option.value)}
                      className={`flex w-full items-start px-3 py-2 text-left text-sm hover:bg-primary-50 ${
                        active ? 'bg-primary-50 font-medium text-primary-800' : 'text-gray-800'
                      }`}
                    >
                      <span className="min-w-0 break-words">{option.label}</span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>,
        document.body,
      )}
    </div>
  );
}
