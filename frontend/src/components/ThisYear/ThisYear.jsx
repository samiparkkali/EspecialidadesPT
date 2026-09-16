import { useMemo, useState } from 'react';
import PortugalMap from '../PortugalMap/PortugalMap';

// Shows the latest year currently loaded, region by region. Once the
// official seat map for the upcoming year is released and parsed into
// vagas.json (see backend/build_dataset.py), it becomes "latest" here
// automatically -- no code change needed, just re-running the pipeline.
const ThisYear = ({ vagas }) => {
  const [selectedRegion, setSelectedRegion] = useState('');
  const [selectedSpecialty, setSelectedSpecialty] = useState('');

  const latestYear = useMemo(() => {
    if (!vagas.length) return null;
    return Math.max(...vagas.map((r) => Number(r.year)));
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

  const byInstitution = useMemo(() => {
    if (!selectedSpecialty) return [];
    const totals = new Map();
    for (const r of filteredRows) {
      if (r.specialty !== selectedSpecialty) continue;
      const name = r.canonical_institution || r.institution;
      totals.set(name, (totals.get(name) || 0) + Number(r.seats));
    }
    return Array.from(totals.entries())
      .map(([institution, seats]) => ({ institution, seats }))
      .sort((a, b) => b.seats - a.seats);
  }, [filteredRows, selectedSpecialty]);

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
          Click a region on the map (or in the list) to filter. This is the
          latest year currently loaded, once a newer one is added, it takes
          over here automatically.
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
            {bySpecialty.map((r) => (
              <tr
                key={r.specialty}
                onClick={() => setSelectedSpecialty(r.specialty === selectedSpecialty ? '' : r.specialty)}
                style={{ cursor: 'pointer', color: r.specialty === selectedSpecialty ? 'var(--color-secondary)' : undefined }}
              >
                <td>{r.specialty}</td>
                <td>{r.seats}</td>
              </tr>
            ))}
            {bySpecialty.length === 0 && (
              <tr>
                <td colSpan={2}>No data for this region yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedSpecialty && (
        <div className="card">
          <h2>
            Hospitals offering {selectedSpecialty}
            {selectedRegion ? ` in ${selectedRegion.replace(/-/g, ' ')}` : ''}
          </h2>
          <table>
            <thead>
              <tr>
                <th>Institution</th>
                <th>Seats</th>
              </tr>
            </thead>
            <tbody>
              {byInstitution.map((r) => (
                <tr key={r.institution}>
                  <td>{r.institution}</td>
                  <td>{r.seats}</td>
                </tr>
              ))}
              {byInstitution.length === 0 && (
                <tr>
                  <td colSpan={2}>No institution breakdown available.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};

export default ThisYear;
