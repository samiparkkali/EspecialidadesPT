import { Fragment, useMemo, useState } from 'react';
import PortugalMap from '../PortugalMap/PortugalMap';
import { useLanguage } from '../../i18n/LanguageContext';

// Shows the latest loaded year region by region; a new year becomes
// "latest" automatically once the pipeline adds it to vagas.json.
const ThisYear = ({ vagas }) => {
  const { t } = useLanguage();
  const [selectedRegion, setSelectedRegion] = useState('');
  const [selectedSpecialty, setSelectedSpecialty] = useState('');

  // Some years only have specialty totals, not institution-level rows this
  // map/drill-down view needs -- pick the latest year that does.
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
      counts[r.region_key] = (counts[r.region_key] || 0) + (Number(r.seats) || 0);
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
      totals.set(r.specialty, (totals.get(r.specialty) || 0) + (Number(r.seats) || 0));
    }
    return Array.from(totals.entries())
      .map(([specialty, seats]) => ({ specialty, seats }))
      .sort((a, b) => a.specialty.localeCompare(b.specialty));
  }, [filteredRows]);

  const institutionsBySpecialty = useMemo(() => {
    const bySpecialtyMap = new Map();
    for (const r of filteredRows) {
      if (!bySpecialtyMap.has(r.specialty)) bySpecialtyMap.set(r.specialty, new Map());
      const totals = bySpecialtyMap.get(r.specialty);
      const name = r.canonical_institution || r.institution;
      totals.set(name, (totals.get(name) || 0) + (Number(r.seats) || 0));
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
        <p className="subtitle">{t.thisYear.noYearData}</p>
      </div>
    );
  }

  return (
    <>
      <div className="card" data-tour="portugal-map">
        <h2>{t.thisYear.seatsAvailable(latestYear)}</h2>
        <p className="subtitle">{t.thisYear.mapHint}</p>
        <PortugalMap
          selected={selectedRegion}
          onSelect={selectRegion}
          counts={seatsByRegion}
        />
      </div>

      <div className="card">
        <h2>
          {t.thisYear.seatsBySpecialty}
          {selectedRegion
            ? t.thisYear.seatsBySpecialtyIn(selectedRegion.replace(/-/g, ' ').toUpperCase())
            : t.thisYear.seatsBySpecialtyAll}
        </h2>
        <p className="subtitle">{t.thisYear.specialtyHint}</p>
        <table>
          <thead>
            <tr>
              <th>{t.thisYear.tableSpecialty}</th>
              <th>{t.thisYear.tableSeats}</th>
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
                              <th>{t.thisYear.tableInstitution}</th>
                              <th>{t.thisYear.tableSeats}</th>
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
                <td colSpan={2}>{t.thisYear.noRegionData}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
};

export default ThisYear;
