import { useMemo, useState } from 'react';
import { useDataset } from './hooks/useDataset';
import Tabs from './components/Tabs/Tabs';
import Filters from './components/Filters/Filters';
import Evolution from './components/Evolution/Evolution';
import Predict from './components/Predict/Predict';
import ThisYear from './components/ThisYear/ThisYear';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'this-year', label: "This Year's Seats" },
];

function App() {
  const { data: vagas, error: vagasError } = useDataset('vagas.json');
  const { data: colocados, error: colocadosError } = useDataset('colocados.json');

  const [activeTab, setActiveTab] = useState('overview');
  const [specialty, setSpecialty] = useState('');
  const [institution, setInstitution] = useState('');

  const specialties = useMemo(() => {
    if (!vagas) return [];
    return [...new Set(vagas.map((r) => r.specialty))].sort();
  }, [vagas]);

  const institutions = useMemo(() => {
    if (!vagas) return [];
    return [...new Set(
      vagas
        .map((r) => r.canonical_institution || r.institution)
        .filter(Boolean)
    )].sort();
  }, [vagas]);

  const evolutionPoints = useMemo(() => {
    if (!vagas) return [];

    // Some years only have specialty-level totals (no institution
    // breakdown, see backend/build_dataset.py's fallback to
    // extract_vagas_totals.py) -- filtering an institution only makes
    // sense for years that actually have institution rows, so per
    // (year, specialty) prefer summing institution rows when present,
    // otherwise fall back to that specialty's single total row
    // (region === '' && institution === '').
    const hasInstitutionData = new Set(
      vagas.filter((r) => r.institution).map((r) => `${r.year}|${r.specialty}`)
    );

    const rows = vagas.filter((r) => {
      const key = `${r.year}|${r.specialty}`;
      if (hasInstitutionData.has(key)) return Boolean(r.institution);
      return !r.region && !r.institution;
    });

    const filtered = rows.filter((r) => {
      if (specialty && r.specialty !== specialty) return false;
      if (institution) {
        // Years without institution data can't be filtered by institution.
        if (!r.institution) return false;
        if ((r.canonical_institution || r.institution) !== institution) return false;
      }
      return true;
    });

    const byYear = new Map();
    for (const r of filtered) {
      const year = Number(r.year);
      byYear.set(year, (byYear.get(year) || 0) + Number(r.seats));
    }
    return Array.from(byYear.entries())
      .map(([year, seats]) => ({ year, seats }))
      .sort((a, b) => a.year - b.year);
  }, [vagas, specialty, institution]);

  if (vagasError || colocadosError) {
    return <p>Failed to load data: {String(vagasError || colocadosError)}</p>;
  }

  if (!vagas || !colocados) {
    return <p>Loading data...</p>;
  }

  return (
    <>
      <h1>Grey&apos;s Internato</h1>
      <p className="subtitle">
        It&apos;s a beautiful day to pick the specialty that will one day let
        you retire early and become a happy plumber. Seat offers and
        placements from Portugal&apos;s Internato Médico, by specialty,
        institution and year, extracted from the official ACSS notices.
      </p>

      <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'overview' && (
        <>
          <Filters
            specialties={specialties}
            institutions={institutions}
            specialty={specialty}
            institution={institution}
            onSpecialtyChange={setSpecialty}
            onInstitutionChange={setInstitution}
          />

          <Evolution points={evolutionPoints} />

          <Predict colocados={colocados} />
        </>
      )}

      {activeTab === 'this-year' && <ThisYear vagas={vagas} />}

      <footer className="site-footer">
        <a href="https://parkkali-website.vercel.app/" target="_blank" rel="noopener noreferrer">
          Sami Parkkali
        </a>
      </footer>
    </>
  );
}

export default App;
