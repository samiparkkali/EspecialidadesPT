import { useId, useState } from 'react';
import styles from './SearchableSelect.module.css';

// A type-to-search filter: type into the box, pick a match from the native
// datalist dropdown, and the box clears itself so you can immediately type
// the next search. The active selection shows as a chip below with its own
// clear button, instead of staying in the text field.
const SearchableSelect = ({ label, options, value, onChange, placeholder }) => {
  const [query, setQuery] = useState('');
  const listId = useId();

  const handleChange = (e) => {
    const next = e.target.value;
    if (options.includes(next)) {
      onChange(next);
      setQuery('');
    } else {
      setQuery(next);
    }
  };

  return (
    <label>
      {label}
      <input
        list={listId}
        value={query}
        onChange={handleChange}
        placeholder={placeholder || 'Escrever para pesquisar...'}
      />
      <datalist id={listId}>
        {options.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
      {value ? (
        <span className={styles.chip}>
          {value}
          <button type="button" onClick={() => onChange('')} aria-label={`Remover filtro ${label}`}>
            &times;
          </button>
        </span>
      ) : (
        <span className={styles.chipMuted}>Todas / todos</span>
      )}
    </label>
  );
};

export default SearchableSelect;
