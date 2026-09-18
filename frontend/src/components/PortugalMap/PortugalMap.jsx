import styles from './PortugalMap.module.css';
import { colorForRegion } from '../../utils/regionColors';

// Real ARS (health region) boundaries: Eurostat GISCO's NUTS3 2021 shapes
// grouped into the 5 mainland ARS regions, simplified and projected to this
// viewBox with shapely as a one-off derived asset (not regenerated at build time).
const MAINLAND_VIEWPORT = [228.6, 460];

const REGIONS = [
  {
    key: 'norte',
    label: 'NORTE',
    labelPos: { x: 135.9, y: 63.6 },
    d: 'M85.6,125.4 L69.7,123.7 L60.1,107.8 L49.4,51.4 L46.0,28.6 L63.1,13.0 L90.6,4.0 L97.0,14.2 L90.8,24.0 L92.9,33.3 L100.5,33.1 L121.9,26.0 L143.3,32.5 L157.8,28.0 L160.5,19.8 L172.2,20.0 L197.9,23.4 L203.6,43.1 L217.7,47.4 L224.6,55.6 L215.3,71.5 L210.6,74.6 L208.6,78.2 L192.1,86.8 L184.1,99.9 L176.0,102.1 L161.1,110.1 L157.7,102.9 L150.6,103.1 L140.7,121.0 L126.2,116.1 L122.4,109.0 L109.7,103.0 L98.0,105.8 L95.5,115.9 L85.6,125.4 Z',
  },
  {
    key: 'centro',
    label: 'CENTRO',
    labelPos: { x: 109.5, y: 173.7 },
    d: 'M70.7,207.6 L60.0,212.7 L57.5,230.9 L52.9,237.7 L43.2,238.5 L41.2,221.3 L34.0,214.5 L43.8,188.0 L51.3,146.5 L57.8,131.6 L60.1,107.8 L69.7,123.7 L85.6,125.4 L95.5,115.9 L98.0,105.8 L109.7,103.0 L122.4,109.0 L126.2,116.1 L140.7,121.0 L150.6,103.1 L157.7,102.9 L161.1,110.1 L176.0,102.1 L183.8,119.1 L184.6,160.4 L180.3,168.3 L174.5,169.5 L170.9,178.0 L179.4,194.1 L169.6,219.3 L134.7,221.3 L115.8,232.3 L106.6,218.2 L108.0,204.4 L98.2,196.9 L96.0,197.7 L77.2,213.7 L70.7,207.6 Z',
  },
  {
    key: 'lisboa-vale-tejo',
    label: 'LISBOA E VALE DO TEJO',
    labelPos: { x: 52.0, y: 258.9 },
    d: 'M61.0,318.5 L54.6,321.4 L24.6,328.5 L20.1,310.9 L4.0,301.6 L13.8,248.8 L27.3,233.3 L34.0,214.5 L41.2,221.3 L43.2,238.5 L52.9,237.7 L57.5,230.9 L60.0,212.7 L70.7,207.6 L77.2,213.7 L96.0,197.7 L98.2,196.9 L108.0,204.4 L106.6,218.2 L115.8,232.3 L106.4,232.3 L106.2,244.0 L82.4,269.0 L88.7,280.3 L88.7,292.9 L79.4,292.0 L67.2,299.8 L68.7,304.3 L61.0,318.5 Z',
  },
  {
    key: 'alentejo',
    label: 'ALENTEJO',
    labelPos: { x: 102.7, y: 323.9 },
    d: 'M170.4,362.9 L155.4,369.5 L136.8,407.7 L118.6,412.1 L98.8,424.9 L78.6,416.4 L72.4,420.0 L50.4,415.0 L50.3,378.7 L45.8,368.4 L54.6,321.4 L61.0,318.5 L68.7,304.3 L67.2,299.8 L79.4,292.0 L88.7,292.9 L88.7,280.3 L82.4,269.0 L106.2,244.0 L106.4,232.3 L115.8,232.3 L134.7,221.3 L150.1,239.4 L155.7,254.9 L162.7,268.5 L173.4,276.4 L166.7,292.6 L157.6,300.9 L150.5,326.4 L164.0,350.0 L175.8,348.2 L170.4,362.9 Z',
  },
  {
    key: 'algarve',
    label: 'ALGARVE',
    labelPos: { x: 93.6, y: 431.0 },
    d: 'M144.2,438.4 L111.6,456.0 L92.3,446.7 L65.0,443.7 L39.6,452.0 L42.7,437.1 L50.4,415.0 L72.4,420.0 L78.6,416.4 L98.8,424.9 L118.6,412.1 L136.8,407.7 L144.2,438.4 Z',
  },
];

// Açores/Madeira keep their real relative shapes (multiple islands, one path
// each) but are drawn in their own inset viewBox since true-to-scale
// placement in the Atlantic would put them far off the mainland canvas.
const ISLANDS = {
  acores: {
    label: 'AÇORES',
    viewport: [151.8, 90],
    labelPos: { x: 93.8, y: 43.8 },
    d: 'M144.7,85.3 L147.9,84.4 L148.8,87.0 L145.1,86.5 L144.7,85.3 Z M139.2,60.4 L143.0,59.2 L145.7,59.6 L145.9,61.7 L145.2,62.8 L143.3,62.7 L140.5,63.7 L137.2,63.9 L135.9,62.8 L132.8,63.0 L129.5,60.2 L129.2,59.3 L130.8,57.8 L133.0,59.8 L135.5,60.7 L137.7,59.7 L139.2,60.4 Z M67.0,41.7 L66.3,39.9 L67.0,38.8 L70.0,38.4 L74.9,41.4 L78.1,42.0 L78.2,43.1 L68.7,42.7 L67.0,41.7 Z M62.6,36.0 L65.3,37.6 L64.6,39.6 L61.7,39.6 L60.2,37.6 L62.6,36.0 Z M78.6,37.3 L74.0,34.9 L73.9,34.2 L74.4,33.7 L78.6,35.2 L84.2,38.4 L83.2,39.3 L80.5,37.6 L78.6,37.3 Z M94.3,34.7 L93.7,32.9 L94.7,31.6 L96.5,31.3 L100.1,31.8 L101.5,33.3 L100.7,36.0 L96.1,35.8 L94.3,34.7 Z M77.1,23.3 L79.4,22.5 L80.8,25.1 L78.2,25.0 L77.1,23.3 Z M3.8,9.9 L6.5,11.7 L5.3,14.4 L3.5,14.4 L3.0,12.0 L3.8,9.9 Z M7.8,3.4 L7.8,5.6 L6.5,6.7 L5.6,4.5 L6.2,3.0 L7.8,3.4 Z',
  },
  madeira: {
    label: 'MADEIRA',
    viewport: [32.2, 70],
    labelPos: { x: 10.8, y: 15.5 },
    d: 'M29.2,67.0 L27.2,66.5 L27.6,64.9 L28.6,64.7 L29.2,67.0 Z M9.6,9.1 L11.1,10.5 L12.4,11.0 L10.9,13.3 L8.9,13.4 L4.0,11.2 L3.0,9.5 L4.3,8.3 L6.9,9.7 L9.6,9.1 Z M18.5,4.5 L20.1,3.0 L20.9,3.2 L20.9,4.5 L19.2,5.1 L18.5,4.5 Z',
  },
};

// Layout constants for placing the mainland + inset boxes in one shared viewBox.
const CANVAS_WIDTH = 260;
const MAINLAND_X = (CANVAS_WIDTH - MAINLAND_VIEWPORT[0]) / 2;
const INSET_HEIGHT = 60;
const INSET_GAP = 14;
const acoresInsetWidth = (ISLANDS.acores.viewport[0] / ISLANDS.acores.viewport[1]) * INSET_HEIGHT;
const madeiraInsetWidth = (ISLANDS.madeira.viewport[0] / ISLANDS.madeira.viewport[1]) * INSET_HEIGHT;
const insetsTotalWidth = acoresInsetWidth + madeiraInsetWidth + INSET_GAP;
const INSETS_Y = MAINLAND_VIEWPORT[1] + 16;
const CANVAS_HEIGHT = INSETS_Y + INSET_HEIGHT + 8;
const acoresInsetX = (CANVAS_WIDTH - insetsTotalWidth) / 2;
const madeiraInsetX = acoresInsetX + acoresInsetWidth + INSET_GAP;

const PortugalMap = ({ selected, onSelect, counts }) => {
  const isActive = (key) => selected === key;
  const seatsFor = (key) => counts?.[key] ?? 0;

  const regionClass = (key) =>
    `${styles.region} ${isActive(key) ? styles.regionActive : ''}`;

  const toggle = (key) => onSelect(isActive(key) ? '' : key);

  return (
    <div className={styles.wrapper}>
      <svg
        viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label="Map of Portugal by health region"
      >
        <g transform={`translate(${MAINLAND_X}, 0)`}>
          {REGIONS.map((r) => (
            <g key={r.key} onClick={() => toggle(r.key)} className={styles.clickable}>
              <path d={r.d} className={regionClass(r.key)} style={{ '--region-fill': colorForRegion(r.key) }} />
              <title>{r.label} ({seatsFor(r.key)} seats)</title>
            </g>
          ))}
          {REGIONS.map((r) => (
            <text
              key={`label-${r.key}`}
              x={r.labelPos.x}
              y={r.labelPos.y}
              textAnchor="middle"
              className={styles.regionLabel}
              style={{ pointerEvents: 'none' }}
            >
              {seatsFor(r.key)}
            </text>
          ))}
        </g>

        {[
          { key: 'acores', x: acoresInsetX, width: acoresInsetWidth },
          { key: 'madeira', x: madeiraInsetX, width: madeiraInsetWidth },
        ].map(({ key, x, width }) => {
          const island = ISLANDS[key];
          return (
            <g key={key}>
              <rect x={x} y={INSETS_Y} width={width} height={INSET_HEIGHT} rx="4" className={styles.insetBox} />
              <svg x={x} y={INSETS_Y} width={width} height={INSET_HEIGHT} viewBox={`0 0 ${island.viewport[0]} ${island.viewport[1]}`}>
                <g onClick={() => toggle(key)} className={styles.clickable}>
                  <path d={island.d} className={regionClass(key)} style={{ '--region-fill': colorForRegion(key) }} />
                  <title>{island.label} ({seatsFor(key)} seats)</title>
                </g>
                <text
                  x={island.labelPos.x}
                  y={island.labelPos.y}
                  textAnchor="middle"
                  className={styles.regionLabel}
                  style={{ pointerEvents: 'none' }}
                >
                  {seatsFor(key)}
                </text>
              </svg>
              <text x={x + width / 2} y={INSETS_Y - 4} textAnchor="middle" className={styles.insetLabel}>
                {island.label}
              </text>
            </g>
          );
        })}
      </svg>

      <ul className={styles.legend}>
        {[...REGIONS, { key: 'acores', label: 'AÇORES' }, { key: 'madeira', label: 'MADEIRA' }].map((r) => (
          <li
            key={r.key}
            className={isActive(r.key) ? styles.legendItemActive : styles.legendItem}
            onClick={() => toggle(r.key)}
          >
            <span className={styles.legendSwatch} style={{ background: colorForRegion(r.key) }} />
            {r.label}: {seatsFor(r.key)}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PortugalMap;
