import { useId, useRef, useState } from 'react';
import styles from './SearchableSelect.module.css';

// Own listbox instead of a native <datalist> -- datalist renders as a
// browser-native popup that looks and behaves inconsistently across
// browsers (a "floating box" detached from our styling); this stays a
// plain, always-same-place panel anchored right under the input.
const SearchableSelect = ({ label, options, value, onChange, placeholder, getLabel = (o) => o, multiple = false }) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const listId = useId();
  const blurTimeout = useRef(null);
  const optionRefs = useRef([]);

  // Clear stale typed text when `value` changes externally (e.g. a parent resets an invalid selection).
  // Done during render, not an effect, to avoid an extra render pass.
  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    if (query !== '') setQuery('');
  }

  const selected = multiple ? value || [] : value;
  const isSelected = (o) => (multiple ? selected.includes(o) : o === value);

  const filtered = query
    ? options.filter((o) => getLabel(o).toLowerCase().includes(query.toLowerCase())).slice(0, 50)
    : options.slice(0, 50);

  const pick = (option) => {
    if (multiple) {
      onChange(selected.includes(option) ? selected.filter((o) => o !== option) : [...selected, option]);
      setQuery('');
      return;
    }
    onChange(option);
    setQuery('');
    setIsOpen(false);
    setActiveIndex(-1);
  };

  const removeOne = (option) => onChange(selected.filter((o) => o !== option));

  const handleBlur = () => {
    blurTimeout.current = setTimeout(() => {
      setIsOpen(false);
      setActiveIndex(-1);
    }, 150);
  };

  const handleFocus = () => {
    clearTimeout(blurTimeout.current);
    setIsOpen(true);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        return;
      }
      setActiveIndex((i) => {
        const next = Math.min(filtered.length - 1, i + 1);
        optionRefs.current[next]?.scrollIntoView({ block: 'nearest' });
        return next;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => {
        const next = Math.max(0, i - 1);
        optionRefs.current[next]?.scrollIntoView({ block: 'nearest' });
        return next;
      });
    } else if (e.key === 'Enter') {
      if (isOpen && activeIndex >= 0 && filtered[activeIndex]) {
        e.preventDefault();
        pick(filtered[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  };

  return (
    <label className={styles.wrapper}>
      {label}
      <div className={styles.comboBox}>
        <input
          id={listId}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIndex(-1);
            setIsOpen(true);
          }}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || 'Type to search...'}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `${listId}-opt-${activeIndex}` : undefined}
        />
        {isOpen && (
          <ul className={styles.listbox} role="listbox">
            {filtered.length === 0 && <li className={styles.empty}>No matches</li>}
            {filtered.map((o, i) => (
              <li
                key={o}
                id={`${listId}-opt-${i}`}
                ref={(el) => {
                  optionRefs.current[i] = el;
                }}
                role="option"
                aria-selected={isSelected(o)}
                className={[isSelected(o) ? styles.optionActive : styles.option, i === activeIndex ? styles.optionHighlighted : '']
                  .filter(Boolean)
                  .join(' ')}
                onMouseDown={() => pick(o)}
                onMouseEnter={() => setActiveIndex(i)}
              >
                {getLabel(o)}
              </li>
            ))}
          </ul>
        )}
      </div>
      {multiple ? (
        <span className={styles.chipRow}>
          {selected.length === 0 && <span className={styles.chipMuted}>All</span>}
          {selected.map((o) => (
            <span key={o} className={styles.chip}>
              {getLabel(o)}
              <button type="button" onClick={() => removeOne(o)} aria-label={`Remove ${getLabel(o)} from ${label} filter`}>
                &times;
              </button>
            </span>
          ))}
        </span>
      ) : value ? (
        <span className={styles.chip}>
          {getLabel(value)}
          <button type="button" onClick={() => onChange('')} aria-label={`Clear ${label} filter`}>
            &times;
          </button>
        </span>
      ) : (
        <span className={styles.chipMuted}>All</span>
      )}
    </label>
  );
};

export default SearchableSelect;
