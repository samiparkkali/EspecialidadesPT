import styles from './PortugalMap.module.css';
import { colorForRegion } from '../../utils/regionColors';

// Freehand approximation of mainland Portugal's coastline (not survey-accurate
// GPS data), shaped to resemble the real country rather than plain boxes.
const REGIONS = [
  {
    key: 'norte',
    label: 'NORTE',
    labelPos: { x: 150, y: 130 },
    d: `M118,40
        C150,20 190,15 205,32
        C225,55 240,80 238,110
        C236,150 225,190 222,225
        C180,218 130,215 88,230
        C90,190 92,170 90,150
        C89,110 100,65 118,40 Z`,
  },
  {
    key: 'centro',
    label: 'CENTRO',
    labelPos: { x: 150, y: 262 },
    d: `M88,230
        C130,215 180,218 222,225
        C224,250 220,280 218,300
        C180,293 140,288 100,300
        C102,285 102,275 102,265
        C100,250 88,240 88,230 Z`,
  },
  {
    key: 'lisboa-vale-tejo',
    label: 'LISBOA E VALE DO TEJO',
    labelPos: { x: 156, y: 318 },
    d: `M100,300
        C140,288 180,293 218,300
        C216,312 214,322 212,335
        C175,330 135,332 94,345
        C96,335 98,318 100,300 Z`,
  },
  {
    key: 'alentejo',
    label: 'ALENTEJO',
    labelPos: { x: 155, y: 375 },
    d: `M94,345
        C135,332 175,330 212,335
        C220,345 234,360 238,375
        C234,392 226,405 216,415
        C170,408 125,405 82,410
        C80,398 80,388 80,380
        C82,365 90,352 94,345 Z`,
  },
  {
    key: 'algarve',
    label: 'ALGARVE',
    labelPos: { x: 152, y: 452 },
    d: `M82,410
        C125,405 170,408 216,415
        C219,432 221,450 222,468
        C200,478 175,480 150,478
        C120,476 100,470 92,460
        C84,445 80,425 82,410 Z`,
  },
];

// Açores/Madeira drawn at heavily exaggerated scale (same convention printed
// choropleth maps use) -- true-to-scale islands would be near-invisible flecks.
const ISLANDS = {
  acores: {
    label: 'AÇORES',
    box: { x: 4, y: 250, width: 100, height: 80 },
    labelPos: { x: 54, y: 344 },
    shapes: [
      'M14,285 C10,282 10,278 14,276 C18,274 22,277 21,281 C20,285 18,288 14,285 Z',
      'M28,296 C24,292 25,286 30,284 C36,282 41,286 40,291 C39,297 33,301 28,296 Z',
      'M46,290 C43,286 44,281 49,280 C54,279 58,283 56,288 C55,293 49,295 46,290 Z',
      'M62,300 C58,296 59,290 65,289 C71,288 75,293 73,298 C72,303 66,305 62,300 Z',
      'M80,282 C77,278 78,273 83,272 C88,271 91,275 90,280 C89,285 84,287 80,282 Z',
    ],
  },
  madeira: {
    label: 'MADEIRA',
    box: { x: 4, y: 400, width: 100, height: 70 },
    labelPos: { x: 54, y: 462 },
    shapes: [
      'M20,428 C14,424 15,417 23,415 C34,412 46,416 47,422 C48,428 38,433 28,432 C24,432 22,430 20,428 Z',
      'M62,418 C60,416 61,414 64,414 C67,414 68,417 66,419 C64,421 63,420 62,418 Z',
    ],
  },
};

const PortugalMap = ({ selected, onSelect, counts }) => {
  const isActive = (key) => selected === key;
  const seatsFor = (key) => counts?.[key] ?? 0;

  const regionClass = (key) =>
    `${styles.region} ${isActive(key) ? styles.regionActive : ''}`;

  const toggle = (key) => onSelect(isActive(key) ? '' : key);

  return (
    <div className={styles.wrapper}>
      <svg viewBox="0 0 320 490" className={styles.svg} role="img" aria-label="Map of Portugal by health region">
        {REGIONS.map((r) => (
          <g key={r.key} onClick={() => toggle(r.key)} className={styles.clickable}>
            <path d={r.d} className={regionClass(r.key)} style={{ '--region-fill': colorForRegion(r.key) }} />
            <title>{r.label} ({seatsFor(r.key)} seats)</title>
          </g>
        ))}

        {Object.entries(ISLANDS).map(([key, island]) => (
          <g key={key}>
            <rect
              x={island.box.x}
              y={island.box.y}
              width={island.box.width}
              height={island.box.height}
              rx="6"
              className={styles.insetBox}
            />
            <g onClick={() => toggle(key)} className={styles.clickable}>
              {island.shapes.map((d, i) => (
                <path key={i} d={d} className={regionClass(key)} style={{ '--region-fill': colorForRegion(key) }} />
              ))}
              <title>{island.label} ({seatsFor(key)} seats)</title>
            </g>
            <text x={island.labelPos.x} y={island.labelPos.y} textAnchor="middle" className={styles.insetLabel}>
              {island.label}
            </text>
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
        {Object.entries(ISLANDS).map(([key, island]) => (
          <text
            key={`label-${key}`}
            x={island.box.x + island.box.width / 2}
            y={island.box.y + 16}
            textAnchor="middle"
            className={styles.regionLabel}
            style={{ pointerEvents: 'none' }}
          >
            {seatsFor(key)}
          </text>
        ))}
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
