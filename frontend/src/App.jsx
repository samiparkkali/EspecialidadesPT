import { useEffect, useMemo, useRef, useState } from 'react';
import { useDataset } from './hooks/useDataset';
import Tabs from './components/Tabs/Tabs';
import Filters from './components/Filters/Filters';
import Evolution from './components/Evolution/Evolution';
import Predict from './components/Predict/Predict';
import ThisYear from './components/ThisYear/ThisYear';
import RankMyPreferences from './components/RankMyPreferences/RankMyPreferences';
import SpecialtyStats from './components/SpecialtyStats/SpecialtyStats';
import Spinner from './components/Spinner/Spinner';
import Tour from './components/Tour/Tour';

// Single source of truth for the site name -- mirrored to the tab title since index.html's <title> is static.
const SITE_TITLE = 'Internato Impossible';

function App() {
  const { data: vagas, error: vagasError } = useDataset('vagas.json');
  const { data: colocados, error: colocadosError } = useDataset('colocados.json');

  const [activeTab, setActiveTab] = useState('overview');
  const [specialty, setSpecialty] = useState('');
  const [institution, setInstitution] = useState('');

  // Same "latest year with institution-level rows" logic ThisYear uses -- keeps
  // the mobile tab label in sync with whatever year that view actually shows.
  const latestYear = useMemo(() => {
    if (!vagas) return null;
    const years = vagas.filter((r) => r.institution).map((r) => Number(r.year));
    return years.length ? Math.max(...years) : null;
  }, [vagas]);

  const TABS = useMemo(
    () => [
      { id: 'overview', label: 'Overview', shortLabel: 'Overview' },
      { id: 'this-year', label: "This Year's Seats", shortLabel: latestYear ? `Year ${latestYear}` : 'This Year' },
      { id: 'specialty-stats', label: 'Specialty Statistics', shortLabel: 'Statistics' },
      { id: 'rank-preferences', label: 'Rank My Preferences', shortLabel: 'Ranking' },
    ],
    [latestYear]
  );

  useEffect(() => {
    document.title = SITE_TITLE;
  }, []);

  // Swipe left/right between tabs, ignored if the touch started on something horizontally scrollable (chart/table).
  const touchStart = useRef(null);
  const handleTouchStart = (e) => {
    const target = e.target.closest('[data-h-scroll]');
    if (target && target.scrollWidth > target.clientWidth) {
      touchStart.current = null;
      return;
    }
    const t = e.touches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  };
  const handleTouchEnd = (e) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    const idx = TABS.findIndex((tab) => tab.id === activeTab);
    if (idx === -1) return;
    const nextIdx = dx < 0 ? idx + 1 : idx - 1;
    if (nextIdx < 0 || nextIdx >= TABS.length) return;
    setActiveTab(TABS[nextIdx].id);
  };

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

    // Rows are already leaf-level (build_dataset.py's _leaf_rows_only), so summing here can't double-count.
    const filtered = vagas.filter((r) => {
      if (specialty && r.specialty !== specialty) return false;
      if (institution) {
        if (!r.institution) return false;
        if ((r.canonical_institution || r.institution) !== institution) return false;
      }
      return true;
    });

    const byYear = new Map();
    for (const r of filtered) {
      const year = Number(r.year);
      byYear.set(year, (byYear.get(year) || 0) + (Number(r.seats) || 0));
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
      <h1>{SITE_TITLE}</h1>
      <p className="subtitle">
        It&apos;s a beautiful day to pick the specialty that will one day let
        you retire early and become a happy plumber. Seat offers and
        placements from Portugal&apos;s Internato Médico, by specialty,
        institution and year, extracted from the official ACSS notices.
      </p>

      <div className="tabs-row">
        <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
        <Tour activeTab={activeTab} onChangeTab={setActiveTab} />
      </div>

      <div onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
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

          <Predict vagas={vagas} colocados={colocados} />
        </>
      )}

      {activeTab === 'this-year' && <ThisYear vagas={vagas} />}

      {activeTab === 'specialty-stats' && <SpecialtyStats vagas={vagas} />}

      {activeTab === 'rank-preferences' && <RankMyPreferences vagas={vagas} colocados={colocados} />}
      </div>

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
