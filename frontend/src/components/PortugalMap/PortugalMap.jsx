import styles from './PortugalMap.module.css';

// Schematic (not geographically precise) map: mainland as 5 horizontal
// bands north to south, Açores and Madeira as inset boxes below/beside it
// -- the same convention official Portuguese maps use, since the
// archipelagos sit far out in the Atlantic and wouldn't fit to scale.
const REGIONS = [
  { key: 'norte', label: 'Norte', d: 'M70 20 L230 20 L220 90 L80 90 Z' },
  { key: 'centro', label: 'Centro', d: 'M80 90 L220 90 L205 170 L95 170 Z' },
  { key: 'lisboa-vale-tejo', label: 'Lisboa e Vale do Tejo', d: 'M95 170 L205 170 L195 225 L105 225 Z' },
  { key: 'alentejo', label: 'Alentejo', d: 'M105 225 L195 225 L180 310 L120 310 Z' },
  { key: 'algarve', label: 'Algarve', d: 'M120 310 L180 310 L185 345 L115 345 Z' },
];

const PortugalMap = ({ selected, onSelect, counts }) => {
  const isActive = (key) => selected === key;
  const seatsFor = (key) => counts?.[key] ?? 0;

  const regionClass = (key) =>
    `${styles.region} ${isActive(key) ? styles.regionActive : ''}`;

  return (
    <div className={styles.wrapper}>
      <svg viewBox="0 0 300 400" className={styles.svg} role="img" aria-label="Map of Portugal by health region">
        {REGIONS.map((r) => (
          <g key={r.key} onClick={() => onSelect(isActive(r.key) ? '' : r.key)} className={styles.clickable}>
            <path d={r.d} className={regionClass(r.key)} />
            <title>{r.label} ({seatsFor(r.key)} seats)</title>
          </g>
        ))}

        {/* Açores inset */}
        <g onClick={() => onSelect(isActive('acores') ? '' : 'acores')} className={styles.clickable}>
          <rect x="15" y="345" width="90" height="45" rx="4" className={styles.insetBox} />
          <circle cx="35" cy="368" r="6" className={regionClass('acores')} />
          <circle cx="55" cy="372" r="7" className={regionClass('acores')} />
          <circle cx="78" cy="366" r="6" className={regionClass('acores')} />
          <title>Açores ({seatsFor('acores')} seats)</title>
        </g>
        <text x="60" y="398" textAnchor="middle" className={styles.insetLabel}>Açores</text>

        {/* Madeira inset */}
        <g onClick={() => onSelect(isActive('madeira') ? '' : 'madeira')} className={styles.clickable}>
          <rect x="195" y="345" width="90" height="45" rx="4" className={styles.insetBox} />
          <ellipse cx="240" cy="368" rx="16" ry="7" className={regionClass('madeira')} />
          <title>Madeira ({seatsFor('madeira')} seats)</title>
        </g>
        <text x="240" y="398" textAnchor="middle" className={styles.insetLabel}>Madeira</text>

        {REGIONS.map((r) => {
          const [, yStr] = r.d.match(/M[\d.]+ ([\d.]+)/) || [];
          return (
            <text
              key={`label-${r.key}`}
              x="150"
              y={Number(yStr) + 35}
              textAnchor="middle"
              className={styles.regionLabel}
              style={{ pointerEvents: 'none' }}
            >
              {seatsFor(r.key)}
            </text>
          );
        })}
      </svg>

      <ul className={styles.legend}>
        {[...REGIONS, { key: 'acores', label: 'Açores' }, { key: 'madeira', label: 'Madeira' }].map((r) => (
          <li
            key={r.key}
            className={isActive(r.key) ? styles.legendItemActive : styles.legendItem}
            onClick={() => onSelect(isActive(r.key) ? '' : r.key)}
          >
            {r.label}: {seatsFor(r.key)}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PortugalMap;
