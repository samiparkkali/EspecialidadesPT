import { useMemo, useState } from 'react';
import { useDataset } from './hooks/useDataset';
import Tabs from './components/Tabs/Tabs';
import Filters from './components/Filters/Filters';
import Evolution from './components/Evolution/Evolution';
import Predict from './components/Predict/Predict';
import ThisYear from './components/ThisYear/ThisYear';
import RankMyPreferences from './components/RankMyPreferences/RankMyPreferences';
import SpecialtyStats from './components/SpecialtyStats/SpecialtyStats';
import Spinner from './components/Spinner/Spinner';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'this-year', label: "This Year's Seats" },
  { id: 'specialty-stats', label: 'Specialty Statistics' },
  { id: 'rank-preferences', label: 'Rank My Preferences' },
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
        .filter((r) => !specialty || r.specialty === specialty)
        .map((r) => r.canonical_institution || r.institution)
        .filter(Boolean)
    )].sort();
  }, [vagas, specialty]);

  const evolutionPoints = useMemo(() => {
    if (!vagas) return [];

    // Each row is already leaf-level (build_dataset.py's _leaf_rows_only),
    // so summing directly here can't double-count across granularity levels.
    const filtered = vagas.filter((r) => {
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
    return <Spinner label="Loading seat and placement data..." />;
  }

  return (
    <>
      <h1>
        <img src="/flag-pt.svg" alt="Portugal" width="28" height="19" style={{ verticalAlign: 'middle', marginRight: '0.5rem', borderRadius: '2px' }} />
        Grey&apos;s Internato
      </h1>
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
            onSpecialtyChange={(next) => {
              setSpecialty(next);
              setInstitution((current) => {
                if (!current || !vagas) return current;
                const stillValid = vagas.some(
                  (r) =>
                    (!next || r.specialty === next) &&
                    (r.canonical_institution || r.institution) === current
                );
                return stillValid ? current : '';
              });
            }}
            onInstitutionChange={setInstitution}
          />

          <Evolution points={evolutionPoints} />

          <Predict colocados={colocados} />
        </>
      )}

      {activeTab === 'this-year' && <ThisYear vagas={vagas} />}

      {activeTab === 'specialty-stats' && <SpecialtyStats vagas={vagas} />}

      {activeTab === 'rank-preferences' && <RankMyPreferences vagas={vagas} colocados={colocados} />}

      <footer className="site-footer">
        &copy; {new Date().getFullYear()} All rights reserved. Engineered by{' '}
        <a href="https://parkkali-website.vercel.app/" target="_blank" rel="noopener noreferrer">
          Sami Parkkali
        </a>
      </footer>
    </>
  );
}

export default App;
