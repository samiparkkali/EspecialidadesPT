import { useMemo, useState } from 'react';
import SearchableSelect from '../SearchableSelect/SearchableSelect';
import { regionLabel } from '../../utils/regionLabels';
import styles from './Predict.module.css';

// Cutoffs are shown per-year rather than averaged, since they vary a lot year to year.
const UNKNOWN_INSTITUTION = 'Institution not recorded (OCR year)';

const buildCutoffsByYear = (colocados) => {
  const grouped = new Map();
  for (const row of colocados) {
    const institution = row.canonical_institution || row.institution || UNKNOWN_INSTITUTION;
    const key = `${row.specialty}|||${institution}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        specialty: row.specialty,
        institution,
        cutoffByYear: new Map(),
      });
    }
    const entry = grouped.get(key);
    const year = Number(row.year);
    const ordering = Number(row.ordering_number);
    entry.cutoffByYear.set(year, Math.max(entry.cutoffByYear.get(year) || 0, ordering));
  }
  return Array.from(grouped.values());
};

const DEFAULT_OFFSET = 200;

// Rendering every match (can be 1000+ rows with a low number and no
// specialty/region filter) is what caused the visible input lag on the
// first keystroke -- that's the render that flips `results` from null to a
// huge array and mounts every card/row at once. Capping it keeps the first
// paint cheap; results are already sorted most-competitive-first, so the
// cap only hides the least useful (highest-cutoff) matches.
const RESULTS_DISPLAY_LIMIT = 150;

// Region lookup from ALL years of vagas, so a no-longer-offered institution still resolves to its region.
const buildRegionByInstitution = (vagas) => {
  const map = new Map();
  for (const r of vagas) {
    if (!r.institution) continue;
    const name = r.canonical_institution || r.institution;
    if (!map.has(name)) map.set(name, r.region_key || '');
  }
  return map;
};

const Predict = ({ vagas, colocados }) => {
  const [orderingNumber, setOrderingNumber] = useState('');
  const [offset, setOffset] = useState(String(DEFAULT_OFFSET));
  const [specialtyFilter, setSpecialtyFilter] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
  const groups = useMemo(() => buildCutoffsByYear(colocados), [colocados]);
  const regionByInstitution = useMemo(() => buildRegionByInstitution(vagas), [vagas]);

  const specialties = useMemo(
    () => [...new Set(groups.map((g) => g.specialty))].sort(),
    [groups]
  );

  const regions = useMemo(
    () => [...new Set(vagas.map((r) => r.region_key || '').filter(Boolean))].sort(),
    [vagas]
  );

  const results = useMemo(() => {
    const n = Number(orderingNumber);
    if (!orderingNumber || Number.isNaN(n) || n <= 0) return null;
    const margin = Math.max(0, Number(offset) || 0);

    return groups
      .filter((g) => !specialtyFilter || g.specialty === specialtyFilter)
      .filter((g) => !regionFilter || regionByInstitution.get(g.institution) === regionFilter)
      .map((g) => {
        const years = Array.from(g.cutoffByYear.entries());
        const eligibleYears = years
          .filter(([, cutoff]) => cutoff >= n)
          .map(([year, cutoff]) => ({ year, cutoff }));
        // Judged per year, not the average -- one outlier year can be a near-miss even when the average isn't close.
        const closeYears = years
          .filter(([, cutoff]) => cutoff < n && cutoff >= n - margin)
          .map(([year, cutoff]) => ({ year, cutoff }));
        const avgCutoff = Math.round(
          years.reduce((sum, [, c]) => sum + c, 0) / years.length
        );
        return {
          specialty: g.specialty,
          institution: g.institution,
          avgCutoff,
          eligibleYears: eligibleYears.sort((a, b) => a.year - b.year),
          closeYears: closeYears.sort((a, b) => a.year - b.year),
          totalYears: years.length,
        };
      })
      .filter((r) => r.eligibleYears.length > 0 || r.closeYears.length > 0)
      .sort((a, b) => a.avgCutoff - b.avgCutoff);
  }, [groups, orderingNumber, offset, specialtyFilter, regionFilter, regionByInstitution]);

  return (
    <div className="card" data-tour="predict">
      <h2>What could I get into with this Golden Ticket Number?</h2>
      <p className="subtitle">
        Enter your Golden Ticket Number ("ordem de colocação") to see which specialty/institution combinations it
        would have gotten you into, checked separately against each past year's actual cutoff (the last candidate
        placed that year) rather than a single blended average. It's a lookup against real history, not a forecast.
        Results are ordered by average cutoff, lowest (most competitive) first.
      </p>
      <div className="filters-row">
        <label htmlFor="ordering-input">
          Golden Ticket Number
          <input
            id="ordering-input"
            type="number"
            min="1"
            value={orderingNumber}
            onChange={(e) => setOrderingNumber(e.target.value)}
            placeholder="e.g. 1200"
          />
        </label>

        <label htmlFor="offset-input">
          Offset (+)
          <input
            id="offset-input"
            type="number"
            min="0"
            value={offset}
            onChange={(e) => setOffset(e.target.value)}
          />
        </label>

        <SearchableSelect
          label="Specialty"
          options={specialties}
          value={specialtyFilter}
          onChange={setSpecialtyFilter}
        />

        <SearchableSelect
          label="Region"
          options={regions}
          value={regionFilter}
          onChange={setRegionFilter}
          getLabel={regionLabel}
        />
      </div>
      {orderingNumber && (
        <p className="subtitle">
          "Close call" years use a +{Math.max(0, Number(offset) || 0)} offset:
          years where your Golden Ticket Number would have needed to be up to
          that much better to get in, shown separately from actual matches.
        </p>
      )}

      {results && (
        <>
          {results.length > RESULTS_DISPLAY_LIMIT && (
            <p className="subtitle" style={{ fontSize: '0.72rem' }}>
              Showing the {RESULTS_DISPLAY_LIMIT} most competitive of {results.length} matches. Narrow with the
              specialty/region filters above to see the rest.
            </p>
          )}
          <div className={styles.mobileResults}>
            {results.slice(0, RESULTS_DISPLAY_LIMIT).map((r) => (
              <div key={`${r.specialty}|${r.institution}`} className={styles.resultCard}>
                <div className={styles.resultTitle}>
                  {r.specialty} - {r.institution}
                </div>
                <div className={styles.resultMeta}>
                  Avg cutoff <span className={styles.resultAvg}>{r.avgCutoff}</span>
                  {r.eligibleYears.length > 0 &&
                    ` · in: ${r.eligibleYears.map((y) => `${y.year} (${y.cutoff})`).join(', ')}`}
                  {r.closeYears.length > 0 &&
                    ` · close: ${r.closeYears.map((y) => `${y.year} (${y.cutoff})`).join(', ')}`}
                </div>
              </div>
            ))}
            {results.length === 0 && (
              <p className="subtitle">No matches for this number with the current data. Maybe try plumbing.</p>
            )}
          </div>

          <div data-h-scroll className={styles.desktopTable} style={{ overflowX: 'auto', marginTop: '1rem' }}>
            <table style={{ minWidth: '620px' }}>
              <thead>
                <tr>
                  <th>Specialty</th>
                  <th>Institution</th>
                  <th>Years you'd get in</th>
                  <th>Close calls (+offset)</th>
                  <th>Average cutoff</th>
                </tr>
              </thead>
              <tbody>
                {results.slice(0, RESULTS_DISPLAY_LIMIT).map((r) => (
                  <tr key={`${r.specialty}|${r.institution}`}>
                    <td>{r.specialty}</td>
                    <td>{r.institution}</td>
                    <td>
                      {r.eligibleYears.map((y) => `${y.year} (${y.cutoff})`).join(', ') || '-'}
                      {r.eligibleYears.length > 0 && r.eligibleYears.length < r.totalYears && (
                        <span className="subtitle"> (of {r.totalYears} years with data)</span>
                      )}
                    </td>
                    <td>{r.closeYears.map((y) => `${y.year} (${y.cutoff})`).join(', ') || '-'}</td>
                    <td>{r.avgCutoff}</td>
                  </tr>
                ))}
                {results.length === 0 && (
                  <tr>
                    <td colSpan={5}>No matches for this number with the current data. Maybe try plumbing.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default Predict;
