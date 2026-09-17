import { useId, useRef, useState } from 'react';
import styles from './SearchableSelect.module.css';

// Own listbox instead of a native <datalist> -- datalist renders as a
// browser-native popup that looks and behaves inconsistently across
// browsers (a "floating box" detached from our styling); this stays a
// plain, always-same-place panel anchored right under the input.
const SearchableSelect = ({ label, options, value, onChange, placeholder, getLabel = (o) => o }) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const listId = useId();
  const blurTimeout = useRef(null);
  const optionRefs = useRef([]);

  // Clear stale typed text whenever the committed value changes for any
  // reason other than picking an option here -- e.g. a parent clearing the
  // selection because it became invalid for a newly-changed sibling filter,
  // or this component's own clear ("x") button. Without this, the input
  // keeps showing old typed text that no longer matches the real selection.
  // Adjusted during render (React's recommended pattern for this, using
  // state rather than a ref so it plays well with the compiler) instead of
  // an effect, which would cause an extra render pass every time.
  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    if (query !== '') setQuery('');
  }

  const filtered = query
    ? options.filter((o) => getLabel(o).toLowerCase().includes(query.toLowerCase())).slice(0, 50)
    : options.slice(0, 50);

  const pick = (option) => {
    onChange(option);
    setQuery('');
    setIsOpen(false);
    setActiveIndex(-1);
  };

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
                aria-selected={o === value}
                className={[o === value ? styles.optionActive : styles.option, i === activeIndex ? styles.optionHighlighted : '']
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
      {value ? (
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
