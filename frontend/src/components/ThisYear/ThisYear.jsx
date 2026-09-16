import { Fragment, useMemo, useState } from 'react';
import PortugalMap from '../PortugalMap/PortugalMap';

// Shows the latest year currently loaded, region by region. Once the
// official seat map for the upcoming year is released and parsed into
// vagas.json (see backend/build_dataset.py), it becomes "latest" here
// automatically -- no code change needed, just re-running the pipeline.
const ThisYear = ({ vagas }) => {
  const [selectedRegion, setSelectedRegion] = useState('');
  const [selectedSpecialty, setSelectedSpecialty] = useState('');

  // Picks the latest year that actually has institution-level rows -- some
  // years only have specialty totals (see backend/build_dataset.py), which
  // this map/drill-down view can't do anything with.
  const latestYear = useMemo(() => {
    const years = vagas.filter((r) => r.institution).map((r) => Number(r.year));
    return years.length ? Math.max(...years) : null;
  }, [vagas]);

  const yearRows = useMemo(
    () => vagas.filter((r) => Number(r.year) === latestYear && r.institution),
    [vagas, latestYear]
  );

  const seatsByRegion = useMemo(() => {
    const counts = {};
    for (const r of yearRows) {
      if (!r.region_key) continue;
      counts[r.region_key] = (counts[r.region_key] || 0) + Number(r.seats);
    }
    return counts;
  }, [yearRows]);

  const filteredRows = useMemo(() => {
    if (!selectedRegion) return yearRows;
    return yearRows.filter((r) => r.region_key === selectedRegion);
  }, [yearRows, selectedRegion]);

  const bySpecialty = useMemo(() => {
    const totals = new Map();
    for (const r of filteredRows) {
      totals.set(r.specialty, (totals.get(r.specialty) || 0) + Number(r.seats));
    }
    return Array.from(totals.entries())
      .map(([specialty, seats]) => ({ specialty, seats }))
      .sort((a, b) => b.seats - a.seats);
  }, [filteredRows]);

  const institutionsBySpecialty = useMemo(() => {
    const bySpecialtyMap = new Map();
    for (const r of filteredRows) {
      if (!bySpecialtyMap.has(r.specialty)) bySpecialtyMap.set(r.specialty, new Map());
      const totals = bySpecialtyMap.get(r.specialty);
      const name = r.canonical_institution || r.institution;
      totals.set(name, (totals.get(name) || 0) + Number(r.seats));
    }
    const result = new Map();
    for (const [specialty, totals] of bySpecialtyMap) {
      result.set(
        specialty,
        Array.from(totals.entries())
          .map(([institution, seats]) => ({ institution, seats }))
          .sort((a, b) => b.seats - a.seats)
      );
    }
    return result;
  }, [filteredRows]);

  const selectRegion = (region) => {
    setSelectedRegion(region);
    setSelectedSpecialty('');
  };

  if (!latestYear) {
    return (
      <div className="card">
        <p className="subtitle">
          This year's official seat map hasn't been added yet. It'll show up
          here as soon as it's released and run through the pipeline.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <h2>Seats available for {latestYear}</h2>
        <p className="subtitle">
          Click a region on the map to filter. This is the
          latest year currently loaded.
        </p>
        <PortugalMap
          selected={selectedRegion}
          onSelect={selectRegion}
          counts={seatsByRegion}
        />
      </div>

      <div className="card">
        <h2>
          Seats by specialty
          {selectedRegion ? ` in ${selectedRegion.replace(/-/g, ' ')}` : ' (all of Portugal)'}
        </h2>
        <p className="subtitle">Click a specialty to see which hospitals offer it here.</p>
        <table>
          <thead>
            <tr>
              <th>Specialty</th>
              <th>Seats</th>
            </tr>
          </thead>
          <tbody>
            {bySpecialty.map((r) => {
              const isOpen = r.specialty === selectedSpecialty;
              return (
                <Fragment key={r.specialty}>
                  <tr
                    onClick={() => setSelectedSpecialty(isOpen ? '' : r.specialty)}
                    style={{ cursor: 'pointer', color: isOpen ? 'var(--color-secondary)' : undefined }}
                  >
                    <td>{r.specialty}</td>
                    <td>{r.seats}</td>
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={2} style={{ padding: 0, borderBottom: 'none' }}>
                        <table style={{ margin: '0.25rem 0 0.75rem 1.5rem', width: 'calc(100% - 1.5rem)' }}>
                          <thead>
                            <tr>
                              <th>Institution</th>
                              <th>Seats</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(institutionsBySpecialty.get(r.specialty) || []).map((inst) => (
                              <tr key={inst.institution}>
                                <td>{inst.institution}</td>
                                <td>{inst.seats}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {bySpecialty.length === 0 && (
              <tr>
                <td colSpan={2}>No data for this region yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
};

export default ThisYear;
