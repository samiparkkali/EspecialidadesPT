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
import LanguageToggle from './components/LanguageToggle/LanguageToggle';
import { useLanguage } from './i18n/LanguageContext';

function App() {
  const { t } = useLanguage();
  // Single source of truth for the site name -- mirrored to the tab title since index.html's <title> is static.
  const SITE_TITLE = t.app.siteTitle;
  const { data: vagas, error: vagasError } = useDataset('vagas.json');
  const { data: colocados, error: colocadosError } = useDataset('colocados.json');

  const [activeTab, setActiveTabRaw] = useState('overview');

  // Every user-initiated tab switch (click or swipe) jumps back to the top
  // of the page, so the new tab's content starts in view instead of
  // resuming at whatever scroll depth the previous tab was left at.
  const setActiveTab = (id) => {
    setActiveTabRaw(id);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
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
      { id: 'overview', label: t.tabs.overview.label, shortLabel: t.tabs.overview.shortLabel },
      { id: 'this-year', label: t.tabs.thisYear.label, shortLabel: t.tabs.thisYear.shortLabel(latestYear) },
      { id: 'specialty-stats', label: t.tabs.specialtyStats.label, shortLabel: t.tabs.specialtyStats.shortLabel },
      { id: 'rank-preferences', label: t.tabs.rankPreferences.label, shortLabel: t.tabs.rankPreferences.shortLabel },
    ],
    [latestYear, t]
  );

  useEffect(() => {
    document.title = SITE_TITLE;
  }, [SITE_TITLE]);

  // Swipe left/right between tabs, ignored if the touch started on something horizontally scrollable (chart/table).
  const touchStart = useRef(null);
  const handleTouchStart = (e) => {
    const target = e.target.closest('[data-h-scroll]');
    if (target && target.scrollWidth > target.clientWidth) {
      touchStart.current = null;
      return;
    }
    const touch = e.touches[0];
    touchStart.current = { x: touch.clientX, y: touch.clientY };
  };
  const handleTouchEnd = (e) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start) return;
    const touch = e.changedTouches[0];
    const dx = touch.clientX - start.x;
    const dy = touch.clientY - start.y;
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
    return <p>{t.app.loadError(String(vagasError || colocadosError))}</p>;
  }

  if (!vagas || !colocados) {
    return <Spinner label={t.app.loading} />;
  }

  return (
    <>
      <h1>{SITE_TITLE}</h1>
      <p className="subtitle">{t.app.subtitle}</p>

      <div className="tabs-sticky-region">
      <div className="tab-bar-row">
        <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
        <LanguageToggle />
      </div>
      <div className="tour-row">
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
      </div>

      <footer className="site-footer">
        {t.app.footerPrefix(new Date().getFullYear())}{' '}
        <a href="https://parkkali-website.vercel.app/" target="_blank" rel="noopener noreferrer">
          {t.app.footerAuthor}
        </a>
      </footer>
    </>
  );
}

export default App;
