import { useMemo, useState } from 'react';
import SearchableSelect from '../SearchableSelect/SearchableSelect';
import { colorForRegion } from '../../utils/regionColors';
import styles from './SpecialtyStats.module.css';

const regionLabel = (regionKey) => (regionKey ? regionKey.replace(/-/g, ' ').toUpperCase() : 'UNMAPPED');

const SpecialtyStats = ({ vagas }) => {
  const specialties = useMemo(() => [...new Set(vagas.map((r) => r.specialty))].sort(), [vagas]);
  const [specialty, setSpecialty] = useState(specialties[0] || '');

  const rows = useMemo(
    () => vagas.filter((r) => r.specialty === specialty),
    [vagas, specialty]
  );

  const years = useMemo(() => [...new Set(rows.map((r) => Number(r.year)))].sort((a, b) => a - b), [rows]);

  const totalsByYear = useMemo(
    () => years.map((year) => ({
      year,
      seats: rows.filter((r) => Number(r.year) === year).reduce((sum, r) => sum + (Number(r.seats) || 0), 0),
    })),
    [rows, years]
  );

  const regionKeys = useMemo(
    () => [...new Set(rows.map((r) => r.region_key || ''))].sort(),
    [rows]
  );

  const byYearAndRegion = useMemo(() => {
    const map = new Map();
    for (const year of years) {
      const perRegion = new Map();
      for (const regionKey of regionKeys) {
        const seats = rows
          .filter((r) => Number(r.year) === year && (r.region_key || '') === regionKey)
          .reduce((sum, r) => sum + (Number(r.seats) || 0), 0);
        perRegion.set(regionKey, seats);
      }
      map.set(year, perRegion);
    }
    return map;
  }, [rows, years, regionKeys]);

  // Latest year with any institution-level detail -- some years/specialties
  // (e.g. MGF) only have region-level rows, so this can be an earlier year
  // than `years`'s last entry.
  const latestInstitutionYear = useMemo(() => {
    for (let i = years.length - 1; i >= 0; i -= 1) {
      const hasInstitution = rows.some((r) => Number(r.year) === years[i] && r.institution);
      if (hasInstitution) return years[i];
    }
    return null;
  }, [rows, years]);

  // Every year that has institution-level detail for this specialty, so the
  // table can show each institution's seat trend, not just the latest year.
  const institutionYears = useMemo(
    () => years.filter((year) => rows.some((r) => Number(r.year) === year && r.institution)),
    [rows, years]
  );

  // Grouped by region so the table reads as a browsable hierarchy (region ->
  // institution) instead of one long alphabetical list -- each institution
  // keeps whichever region it was most recently seen under.
  const byInstitutionByRegion = useMemo(() => {
    if (latestInstitutionYear === null) return [];
    const byName = new Map();
    for (const r of rows) {
      if (!r.institution || !institutionYears.includes(Number(r.year))) continue;
      const name = r.canonical_institution || r.institution;
      if (!byName.has(name)) byName.set(name, { byYear: new Map(), regionKey: '', regionYear: -Infinity });
      const entry = byName.get(name);
      const year = Number(r.year);
      entry.byYear.set(year, (entry.byYear.get(year) || 0) + (Number(r.seats) || 0));
      if (year >= entry.regionYear) {
        entry.regionKey = r.region_key || '';
        entry.regionYear = year;
      }
    }
    const byRegion = new Map();
    for (const [institution, entry] of byName.entries()) {
      if (!byRegion.has(entry.regionKey)) byRegion.set(entry.regionKey, []);
      byRegion.get(entry.regionKey).push({
        institution,
        seats: entry.byYear.get(latestInstitutionYear) || 0,
        byYear: entry.byYear,
      });
    }
    return [...byRegion.entries()]
      .map(([regionKey, institutions]) => ({
        regionKey,
        institutions: institutions.sort((a, b) => a.institution.localeCompare(b.institution)),
        totalSeats: institutions.reduce((sum, inst) => sum + inst.seats, 0),
      }))
      .sort((a, b) => regionLabel(a.regionKey).localeCompare(regionLabel(b.regionKey)));
  }, [rows, latestInstitutionYear, institutionYears]);

  if (!specialties.length) {
    return (
      <div className="card">
        <p className="subtitle">No seat data loaded yet.</p>
      </div>
    );
  }

  const maxTotal = Math.max(...totalsByYear.map((p) => p.seats), 1);
  const width = 480;
  const height = 160;
  // Leave headroom above the tallest bar for its value label -- without it,
  // the max-value bar's label sits right at (or above) the chart's own top
  // edge and overlaps whatever is rendered above the chart.
  const topPad = 16;
  const barSlot = width / Math.max(1, totalsByYear.length);

  return (
    <>
      <div className="card" data-tour="specialty-stats">
        <h2>Specialty Statistics</h2>
        <p className="subtitle">
          Pick a specialty to see how its total seat count has moved from {years[0] || '...'} to{' '}
          {years[years.length - 1] || '...'}, and how that count breaks down by region each year.
        </p>
        <SearchableSelect
          label="Specialty"
          options={specialties}
          value={specialty}
          onChange={setSpecialty}
          placeholder="Type to search a specialty..."
        />
      </div>

      {specialty && totalsByYear.length > 0 && (
        <div className="card">
          <h2 className={styles.chartTitle}>Total seats per year: {specialty}</h2>
          <div className={styles.chartScroll} data-h-scroll>
          <svg viewBox={`0 0 ${width} ${height + 24}`} className={styles.chart}>
            {totalsByYear.map((p, i) => {
              const barHeight = (p.seats / maxTotal) * (height - topPad);
              const x = i * barSlot + barSlot * 0.15;
              const barW = barSlot * 0.7;
              return (
                <g key={p.year}>
                  <rect
                    x={x}
                    y={height - barHeight}
                    width={barW}
                    height={barHeight}
                    rx={3}
                    className={styles.bar}
                  />
                  <text x={x + barW / 2} y={height + 14} textAnchor="middle" className={styles.label}>
                    {p.year}
                  </text>
                  <text x={x + barW / 2} y={height - barHeight - 4} textAnchor="middle" className={styles.value}>
                    {p.seats}
                  </text>
                </g>
              );
            })}
          </svg>
          </div>
        </div>
      )}

      {specialty && totalsByYear.length > 0 && (
        <div className="card">
          <h2 className={styles.chartTitle}>Breakdown by region: {specialty}</h2>
          <p className="subtitle">Each bar is one year's seats, stacked by region.</p>
          <div className={styles.chartScroll} data-h-scroll>
          <svg viewBox={`0 0 ${width} ${height + 24}`} className={styles.chart}>
            {years.map((year, i) => {
              const perRegion = byYearAndRegion.get(year);
              const x = i * barSlot + barSlot * 0.15;
              const barW = barSlot * 0.7;
              let yCursor = height;
              return (
                <g key={year}>
                  {regionKeys.map((regionKey) => {
                    const seats = perRegion.get(regionKey) || 0;
                    if (!seats) return null;
                    // Enforce a visible minimum so a 1-seat segment doesn't
                    // collapse to a sliver -- stacks a little taller than
                    // `height` when several segments are that small, which
                    // is an acceptable trade for staying visible/labelable.
                    const segHeight = Math.max(8, (seats / maxTotal) * (height - topPad));
                    yCursor -= segHeight;
                    const segY = yCursor;
                    return (
                      <g key={regionKey || 'unmapped'}>
                        <rect x={x} y={segY} width={barW} height={segHeight} fill={colorForRegion(regionKey)}>
                          <title>{regionLabel(regionKey)}: {seats} seats ({year})</title>
                        </rect>
                        <text
                          x={x + barW / 2}
                          y={segY + segHeight / 2 + 3}
                          textAnchor="middle"
                          className={styles.segmentValue}
                        >
                          {seats}
                        </text>
                      </g>
                    );
                  })}
                  <text x={x + barW / 2} y={height + 14} textAnchor="middle" className={styles.label}>
                    {year}
                  </text>
                </g>
              );
            })}
          </svg>
          </div>
          <ul className={styles.legend}>
            {regionKeys.map((regionKey) => (
              <li key={regionKey || 'unmapped'} className={styles.legendItem}>
                <span className={styles.legendSwatch} style={{ background: colorForRegion(regionKey) }} />
                {regionLabel(regionKey)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {specialty && byInstitutionByRegion.length > 0 && (
        <div className="card">
          <h2 className={styles.chartTitle}>
            Seats by institution: {specialty}
          </h2>
          <p className="subtitle">
            Every year with institution-level detail for this specialty, grouped by region and sorted
            alphabetically by institution.
          </p>
          {byInstitutionByRegion.map((group) => (
            <details key={group.regionKey || 'unmapped'} className={styles.regionGroup} open>
              <summary
                className={styles.regionSummary}
                style={{ borderLeft: `3px solid ${colorForRegion(group.regionKey)}` }}
              >
                {regionLabel(group.regionKey)}
                <span className={styles.regionSummaryMeta}>
                  {group.institutions.length} institution{group.institutions.length === 1 ? '' : 's'} ·{' '}
                  {group.totalSeats} seats in {latestInstitutionYear}
                </span>
              </summary>
              <div className={styles.tableScroll} data-h-scroll>
                <table>
                  <thead>
                    <tr>
                      <th>Institution</th>
                      {institutionYears.map((year) => (
                        <th key={year}>{year}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {group.institutions.map((inst) => (
                      <tr key={inst.institution}>
                        <td>{inst.institution}</td>
                        {institutionYears.map((year) => (
                          <td key={year}>{inst.byYear.get(year) ?? '-'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ))}
        </div>
      )}
    </>
  );
};

export default SpecialtyStats;
