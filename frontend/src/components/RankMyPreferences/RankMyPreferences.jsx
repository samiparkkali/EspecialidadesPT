import { useMemo, useRef, useState } from 'react';
import SearchableSelect from '../SearchableSelect/SearchableSelect';
import { colorForRegion } from '../../utils/regionColors';
import { regionLabel } from '../../utils/regionLabels';
import { useLanguage } from '../../i18n/LanguageContext';
import styles from './RankMyPreferences.module.css';

const LIKELIHOOD_TRIALS = 1000;

// Green (likely to enter) -> yellow -> red (unlikely), for likelihood pct display.
const colorForPct = (pct) => {
  const p = Math.max(0, Math.min(100, pct));
  const hue = (p / 100) * 120; // 0 = red, 120 = green
  return `hsl(${hue}, 70%, 42%)`;
};

// Institution '' means "the whole region aggregate", not a specific hospital.
const comboKey = (specialty, regionKey, institution = '') => `${specialty}|||${regionKey}|||${institution}`;
const baseComboKey = (specialty, regionKey) => `${specialty}|||${regionKey}`;
const cutoffKey = (specialty, institution) => `${specialty}|||${institution}`;

// Weighted random pick -- which institution a region-only preference "means" for a trial, bigger institutions more likely.
const pickWeighted = (items, weightFn) => {
  const total = items.reduce((sum, item) => sum + weightFn(item), 0);
  let r = Math.random() * total;
  for (const item of items) {
    r -= weightFn(item);
    if (r <= 0) return item;
  }
  return items[items.length - 1];
};

// Draws one plausible cutoff from an option's own history, rather than assuming every year needs the same rank.
// Region-only: weight-picks an institution by seats first, then samples its history. null means no data.
const sampleCutoff = (cutoffsByKey, institutionsByCombo, specialty, regionKey, institution) => {
  if (institution) {
    const entries = cutoffsByKey.get(cutoffKey(specialty, institution));
    if (!entries || entries.length === 0) return null;
    return entries[Math.floor(Math.random() * entries.length)][1];
  }
  const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
  const withHistory = institutions.filter((inst) => {
    const entries = cutoffsByKey.get(cutoffKey(specialty, inst.institution));
    return entries && entries.length > 0;
  });
  if (withHistory.length === 0) return null;
  const chosen = pickWeighted(withHistory, (inst) => inst.seats);
  const entries = cutoffsByKey.get(cutoffKey(specialty, chosen.institution));
  return entries[Math.floor(Math.random() * entries.length)][1];
};

// Each option's pct is its own MARGINAL odds, independent of the others -- a safe low-cutoff option near the
// bottom still shows near-100% even if you'd be placed earlier; that effect is summarized once in notPlacedPct.
const computeLikelihood = (preferences, cutoffsByKey, institutionsByCombo, myNumber, offset, maxOrdering) => {
  const perOptionHits = new Array(preferences.length).fill(0);
  const perOptionTrials = new Array(preferences.length).fill(0);
  let notPlaced = 0;
  let undecided = 0;
  for (let t = 0; t < LIKELIHOOD_TRIALS; t++) {
    const drawnNumber = Math.min(
      maxOrdering,
      Math.max(1, myNumber + Math.round((Math.random() * 2 - 1) * offset))
    );
    let placedAny = false;
    let anyData = false;
    for (let i = 0; i < preferences.length; i++) {
      const p = preferences[i];
      const cutoff = sampleCutoff(cutoffsByKey, institutionsByCombo, p.specialty, p.regionKey, p.institution);
      if (cutoff === null) continue;
      anyData = true;
      perOptionTrials[i] += 1;
      if (drawnNumber <= cutoff) {
        perOptionHits[i] += 1;
        placedAny = true;
      }
    }
    if (!placedAny) {
      if (anyData) notPlaced += 1;
      else undecided += 1;
    }
  }
  const decided = LIKELIHOOD_TRIALS - undecided;
  return {
    perOption: preferences.map((p, i) => ({
      ...p,
      hasData: perOptionTrials[i] > 0,
      pct: perOptionTrials[i] ? Math.round((perOptionHits[i] / perOptionTrials[i]) * 100) : 0,
    })),
    notPlacedPct: decided ? Math.round((notPlaced / decided) * 100) : 0,
    noDataAtAll: decided === 0,
  };
};

// Per-institution odds for one region-only combo, sampled the same way computeLikelihood does.
const institutionBreakdownFor = (institutions, specialty, cutoffsByKey, myNumber, offset, maxOrdering) =>
  institutions.map((inst) => {
    const entries = cutoffsByKey.get(cutoffKey(specialty, inst.institution));
    const cutoffText = entries && entries.length ? entries.map(([year, n]) => `${year}: ${n}`).join(' · ') : null;
    let pct = null;
    if (myNumber && entries && entries.length) {
      let hits = 0;
      for (let t = 0; t < LIKELIHOOD_TRIALS; t++) {
        const drawnNumber = Math.min(maxOrdering, Math.max(1, myNumber + Math.round((Math.random() * 2 - 1) * offset)));
        const cutoff = entries[Math.floor(Math.random() * entries.length)][1];
        if (drawnNumber <= cutoff) hits += 1;
      }
      pct = Math.round((hits / LIKELIHOOD_TRIALS) * 100);
    }
    return { institution: inst.institution, seats: inst.seats, cutoffText, pct };
  });

const RankMyPreferences = ({ vagas, colocados }) => {
  const { t } = useLanguage();
  const [preferences, setPreferences] = useState([]);
  const [expandedCombo, setExpandedCombo] = useState(null);
  const [myOrderingNumber, setMyOrderingNumber] = useState('');
  const [spreadOffset, setSpreadOffset] = useState(200);
  const [comboFilter, setComboFilter] = useState('');
  const [specialtyFilter, setSpecialtyFilter] = useState([]);
  const [regionFilter, setRegionFilter] = useState([]);
  const dragIndex = useRef(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const latestYear = useMemo(() => {
    const years = vagas.filter((r) => r.institution).map((r) => Number(r.year));
    return years.length ? Math.max(...years) : null;
  }, [vagas]);

  const yearRows = useMemo(
    () => vagas.filter((r) => Number(r.year) === latestYear && r.institution),
    [vagas, latestYear]
  );

  const allSpecialties = useMemo(
    () => [...new Set(yearRows.map((r) => r.specialty))].sort(),
    [yearRows]
  );

  const allRegions = useMemo(
    () => [...new Set(yearRows.map((r) => r.region_key || ''))].sort(),
    [yearRows]
  );

  // Region-level aggregate seats, purely for display in the browsable pool.
  const seatsByCombo = useMemo(() => {
    const map = new Map();
    for (const r of yearRows) {
      const key = comboKey(r.specialty, r.region_key || '');
      map.set(key, (map.get(key) || 0) + (Number(r.seats) || 0));
    }
    return map;
  }, [yearRows]);

  // Region lookup from ALL years of vagas, so a no-longer-offered institution still resolves to its region.
  const regionByInstitution = useMemo(() => {
    const map = new Map();
    for (const r of vagas) {
      if (!r.institution) continue;
      const name = r.canonical_institution || r.institution;
      if (!map.has(name)) map.set(name, r.region_key || '');
    }
    return map;
  }, [vagas]);

  // Source of truth for both the institution drill-down and the simulation's seat tracking.
  const institutionsByCombo = useMemo(() => {
    const map = new Map();
    for (const r of yearRows) {
      const base = baseComboKey(r.specialty, r.region_key || '');
      if (!map.has(base)) map.set(base, new Map());
      const totals = map.get(base);
      const name = r.canonical_institution || r.institution;
      totals.set(name, (totals.get(name) || 0) + (Number(r.seats) || 0));
    }

    // Union in institutions with cutoff history but no current-year seat, so they don't vanish here (Predict shows them fine).
    const seenBySpecialty = new Map();
    for (const [base, totals] of map) {
      const specialty = base.split('|||')[0];
      if (!seenBySpecialty.has(specialty)) seenBySpecialty.set(specialty, new Set());
      for (const name of totals.keys()) seenBySpecialty.get(specialty).add(name);
    }
    for (const row of colocados) {
      const institution = row.canonical_institution || row.institution;
      if (!institution) continue;
      const seen = seenBySpecialty.get(row.specialty);
      if (seen && seen.has(institution)) continue;
      const regionKey = regionByInstitution.get(institution) || '';
      const base = baseComboKey(row.specialty, regionKey);
      if (!map.has(base)) map.set(base, new Map());
      if (!map.get(base).has(institution)) map.get(base).set(institution, 0);
      if (!seenBySpecialty.has(row.specialty)) seenBySpecialty.set(row.specialty, new Set());
      seenBySpecialty.get(row.specialty).add(institution);
    }

    const result = new Map();
    for (const [base, totals] of map) {
      result.set(
        base,
        Array.from(totals.entries())
          .map(([institution, seats]) => ({ institution, seats }))
          .sort((a, b) => b.seats - a.seats || a.institution.localeCompare(b.institution))
      );
    }
    return result;
  }, [yearRows, colocados, regionByInstitution]);

  // Historical Golden Ticket Number cutoffs per specialty+institution, most recent first -- feeds the likelihood panel.
  const cutoffsByKey = useMemo(() => {
    const map = new Map();
    for (const row of colocados) {
      const institution = row.canonical_institution || row.institution;
      if (!institution) continue;
      const key = cutoffKey(row.specialty, institution);
      if (!map.has(key)) map.set(key, new Map());
      const byYear = map.get(key);
      const year = Number(row.year);
      const ordering = Number(row.ordering_number);
      byYear.set(year, Math.max(byYear.get(year) || 0, ordering));
    }
    const result = new Map();
    for (const [key, byYear] of map) {
      result.set(key, Array.from(byYear.entries()).sort((a, b) => b[0] - a[0]));
    }
    return result;
  }, [colocados]);

  // Region entries show a range across institutions rather than one institution's history.
  const cutoffSummary = (specialty, regionKey, institution) => {
    if (institution) {
      const entries = cutoffsByKey.get(cutoffKey(specialty, institution));
      if (!entries || entries.length === 0) return null;
      return entries.map(([year, n]) => `${year}: ${n}`).join(' · ');
    }
    const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
    // A single-institution region has no range to summarize -- show its full multi-year history instead.
    if (institutions.length === 1) {
      return cutoffSummary(specialty, regionKey, institutions[0].institution);
    }
    const latestPerInstitution = institutions
      .map((inst) => cutoffsByKey.get(cutoffKey(specialty, inst.institution)))
      .filter(Boolean)
      .map((entries) => entries[0]);
    if (latestPerInstitution.length === 0) return null;
    const year = latestPerInstitution[0][0];
    const values = latestPerInstitution.filter((e) => e[0] === year).map((e) => e[1]);
    if (values.length === 0) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    return min === max ? `${year}: ${min}` : `${year}: ${min}–${max}`;
  };

  const availableCombos = useMemo(() => {
    const combos = [];
    for (const specialty of allSpecialties) {
      for (const regionKey of allRegions) {
        const seats = seatsByCombo.get(comboKey(specialty, regionKey)) || 0;
        const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
        // Keep a combo browsable with 0 current seats if some institution in it has cutoff history.
        if (seats > 0 || institutions.length > 0) {
          combos.push({ specialty, regionKey, seats, institutions });
        }
      }
    }
    return combos.sort((a, b) => a.specialty.localeCompare(b.specialty) || a.regionKey.localeCompare(b.regionKey));
  }, [allSpecialties, allRegions, seatsByCombo, institutionsByCombo]);

  const filteredCombos = useMemo(() => {
    const q = comboFilter.trim().toLowerCase();
    return availableCombos.filter((c) => {
      if (specialtyFilter.length && !specialtyFilter.includes(c.specialty)) return false;
      if (regionFilter.length && !regionFilter.includes(c.regionKey)) return false;
      if (!q) return true;
      return c.specialty.toLowerCase().includes(q) || regionLabel(c.regionKey).toLowerCase().includes(q);
    });
  }, [availableCombos, comboFilter, specialtyFilter, regionFilter]);

  const maxOrdering = useMemo(() => {
    const numbers = colocados.map((r) => Number(r.ordering_number)).filter((n) => n > 0);
    return numbers.length ? Math.max(...numbers) : 3000;
  }, [colocados]);

  // A combo is ranked as a whole region OR split into institutions, never both -- the region total covers both.
  const comboEntries = (specialty, regionKey) =>
    preferences.filter((p) => p.specialty === specialty && p.regionKey === regionKey);

  const regionEntryExists = (specialty, regionKey) =>
    comboEntries(specialty, regionKey).some((p) => !p.institution);

  const addPreference = (specialty, regionKey, institution = null) => {
    const entries = comboEntries(specialty, regionKey);
    if (institution) {
      if (entries.some((p) => !p.institution || p.institution === institution)) return;
    } else if (entries.length > 0) {
      return;
    }
    setPreferences([...preferences, { specialty, regionKey, institution }]);
  };

  const removePreference = (index) => {
    setPreferences(preferences.filter((_, i) => i !== index));
  };

  // Lets a browse-list button double as an "undo" for what it just added, so
  // removing a wrong pick doesn't require the scratchpad (hidden on mobile).
  const removePreferenceFor = (specialty, regionKey, institution = null) => {
    setPreferences((prev) => {
      const idx = prev.findIndex(
        (p) => p.specialty === specialty && p.regionKey === regionKey && p.institution === institution
      );
      return idx === -1 ? prev : prev.filter((_, i) => i !== idx);
    });
  };

  // Surfaces each pick's rank number right on its browse-list button, since
  // the scratchpad (the only other place that shows ranking order) is
  // hidden on mobile -- without this there'd be no way to see order at all.
  const preferenceRank = (specialty, regionKey, institution = null) => {
    const idx = preferences.findIndex(
      (p) => p.specialty === specialty && p.regionKey === regionKey && p.institution === institution
    );
    return idx === -1 ? null : idx + 1;
  };

  const movePreference = (index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= preferences.length) return;
    const next = [...preferences];
    [next[index], next[target]] = [next[target], next[index]];
    setPreferences(next);
  };

  const reorderTo = (from, to) => {
    if (from === to || from == null || to == null) return;
    const next = [...preferences];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setPreferences(next);
  };

  const handleDragStart = (index) => {
    dragIndex.current = index;
  };

  const handleDragOver = (index, e) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDrop = (index) => {
    reorderTo(dragIndex.current, index);
    dragIndex.current = null;
    setDragOverIndex(null);
  };

  const myNumber = Number(myOrderingNumber) > 0 ? Math.min(maxOrdering, Number(myOrderingNumber)) : null;
  const clampedOffset = Math.max(1, Number(spreadOffset) || 200);

  // Live odds for the ranking as sketched -- see computeLikelihood above.
  const likelihood = useMemo(() => {
    if (!myNumber || preferences.length === 0) return null;
    return computeLikelihood(preferences, cutoffsByKey, institutionsByCombo, myNumber, clampedOffset, maxOrdering);
  }, [myNumber, preferences, clampedOffset, institutionsByCombo, cutoffsByKey, maxOrdering]);

  // Precomputed once so both panels look up the same result instead of each rolling independent
  // Math.random() trials, which used to show two different percentages for the same thing at once.
  const breakdownsByCombo = useMemo(() => {
    const neededCombos = new Set();
    for (const p of preferences) {
      if (!p.institution) neededCombos.add(baseComboKey(p.specialty, p.regionKey));
    }
    if (likelihood) {
      for (const opt of likelihood.perOption) {
        if (!opt.institution) neededCombos.add(baseComboKey(opt.specialty, opt.regionKey));
      }
    }

    const map = new Map();
    for (const base of neededCombos) {
      const specialty = base.split('|||')[0];
      const institutions = institutionsByCombo.get(base) || [];
      const result = institutionBreakdownFor(institutions, specialty, cutoffsByKey, myNumber, clampedOffset, maxOrdering);
      map.set(base, result);
    }
    return map;
  }, [preferences, likelihood, myNumber, clampedOffset, institutionsByCombo, cutoffsByKey, maxOrdering]);

  const institutionBreakdown = (specialty, regionKey) => breakdownsByCombo.get(baseComboKey(specialty, regionKey)) || [];

  if (!latestYear) {
    return (
      <div className="card">
        <p className="subtitle">
          {t.rankMyPreferences.noYearData}
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="card" data-tour="rank-preferences">
        <h2>{t.rankMyPreferences.heading}</h2>
        <p className="subtitle">
          {t.rankMyPreferences.introTemplate(latestYear)}
        </p>

        <div className={styles.rankLayout}>
          <div className={styles.filterRow} data-tour="rank-filters">
            <SearchableSelect
              label={t.filters.specialty}
              options={allSpecialties}
              value={specialtyFilter}
              onChange={setSpecialtyFilter}
              placeholder={t.rankMyPreferences.specialtyFilterPlaceholder}
              multiple
            />
            <SearchableSelect
              label={t.filters.region}
              options={allRegions}
              value={regionFilter}
              onChange={setRegionFilter}
              placeholder={t.rankMyPreferences.regionFilterPlaceholder}
              getLabel={regionLabel}
              multiple
            />
            <label className={styles.textFilter}>
              {t.rankMyPreferences.searchLabel}
              <input
                type="text"
                placeholder={t.rankMyPreferences.searchPlaceholder}
                value={comboFilter}
                onChange={(e) => setComboFilter(e.target.value)}
              />
            </label>
          </div>

          <div className={styles.browseSection}>
            <h3 className={styles.subheading}>
              {t.rankMyPreferences.browseOptions(filteredCombos.length)}
            </h3>
            <div className={styles.comboList} data-tour="rank-browse">
              {filteredCombos.map((combo) => {
                const base = baseComboKey(combo.specialty, combo.regionKey);
                // Show the expand arrow even for a single institution -- hiding its name behind the region label alone was confusing.
                const hasMultipleInstitutions = combo.institutions.length > 0;
                const regionUsed = regionEntryExists(combo.specialty, combo.regionKey);
                const anyEntryUsed = comboEntries(combo.specialty, combo.regionKey).length > 0;
                const regionCutoff = cutoffSummary(combo.specialty, combo.regionKey, null);
                return (
                  <div key={base} className={styles.comboGroup}>
                    <div className={styles.comboRow}>
                      <button
                        type="button"
                        className={styles.comboItem}
                        style={{ borderLeft: `3px solid ${colorForRegion(combo.regionKey)}` }}
                        onClick={() => {
                          if (regionEntryExists(combo.specialty, combo.regionKey)) {
                            removePreferenceFor(combo.specialty, combo.regionKey, null);
                          } else if (!anyEntryUsed) {
                            addPreference(combo.specialty, combo.regionKey);
                          }
                        }}
                        disabled={anyEntryUsed && !regionEntryExists(combo.specialty, combo.regionKey)}
                        aria-label={
                          regionEntryExists(combo.specialty, combo.regionKey)
                            ? t.rankMyPreferences.removeFromRanking(`${combo.specialty} - ${regionLabel(combo.regionKey)}`)
                            : undefined
                        }
                      >
                        <span className={styles.comboItemTitle}>
                          {(() => {
                            const rank = preferenceRank(combo.specialty, combo.regionKey, null);
                            return rank ? (
                              <span className={styles.rankBadge}>
                                #{rank}
                                <span aria-hidden="true"> &times;</span>
                              </span>
                            ) : null;
                          })()}
                          {combo.specialty} - {regionLabel(combo.regionKey)}
                        </span>
                        <span className={styles.comboItemMeta}>
                          {combo.seats} {t.rankMyPreferences.seats}
                          {regionCutoff && (
                            <span className={styles.cutoffTag}> · {t.rankMyPreferences.lastCutoffs} {regionCutoff}</span>
                          )}
                        </span>
                      </button>
                      {hasMultipleInstitutions && (
                        <button
                          type="button"
                          className={styles.expandButton}
                          onClick={() => setExpandedCombo(expandedCombo === base ? null : base)}
                          aria-label={t.rankMyPreferences.showInstitutions}
                        >
                          {expandedCombo === base ? '▾' : '▸'} {t.rankMyPreferences.showInstitutions.toLowerCase()}
                        </button>
                      )}
                    </div>
                    {hasMultipleInstitutions && expandedCombo === base && (
                      <div className={styles.institutionList}>
                        {combo.institutions.map((inst) => {
                          const used = comboEntries(combo.specialty, combo.regionKey).some(
                            (p) => p.institution === inst.institution
                          );
                          const instCutoff = cutoffSummary(combo.specialty, combo.regionKey, inst.institution);
                          return (
                            <button
                              type="button"
                              key={inst.institution}
                              className={styles.institutionItem}
                              disabled={regionUsed && !used}
                              onClick={() =>
                                used
                                  ? removePreferenceFor(combo.specialty, combo.regionKey, inst.institution)
                                  : addPreference(combo.specialty, combo.regionKey, inst.institution)
                              }
                              aria-label={used ? t.rankMyPreferences.removeInstitutionFromRanking(inst.institution) : undefined}
                            >
                              <span className={styles.comboItemTitle}>
                                {used && (
                                  <span className={styles.rankBadge}>
                                    #{preferenceRank(combo.specialty, combo.regionKey, inst.institution)}
                                    <span aria-hidden="true"> &times;</span>
                                  </span>
                                )}
                                {inst.institution}
                              </span>
                              <span className={styles.comboItemMeta}>
                                {inst.seats} {t.rankMyPreferences.seats}
                                {instCutoff && <span className={styles.cutoffTag}> · {t.rankMyPreferences.lastCutoffs} {instCutoff}</span>}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
              {filteredCombos.length === 0 && (
                <p className="subtitle">{t.rankMyPreferences.noCombosMatch}</p>
              )}
            </div>
          </div>

          <div className={styles.numberSection} data-tour="rank-number">
            <div className={styles.numberRow}>
              <label>
                {t.rankMyPreferences.yourOrderingNumber}
                <input
                  type="number"
                  min="1"
                  required
                  placeholder={t.rankMyPreferences.orderingNumberPlaceholder}
                  value={myOrderingNumber}
                  onChange={(e) => setMyOrderingNumber(e.target.value)}
                />
              </label>
              <label>
                {t.rankMyPreferences.spreadLabel}
                <input
                  type="number"
                  min="1"
                  value={spreadOffset}
                  onChange={(e) => setSpreadOffset(Math.max(1, Number(e.target.value) || 200))}
                />
              </label>
            </div>
            <p className="subtitle" style={{ marginTop: 0 }}>
              {t.rankMyPreferences.spreadHint}
            </p>
            {!myNumber && (
              <p className="subtitle">
                {t.rankMyPreferences.enterNumberPrompt}
              </p>
            )}
          </div>

          <div className={styles.scratchpadSection}>
            <h3 className={styles.subheading}>{t.rankMyPreferences.yourRanking(preferences.length)}</h3>
            <p className="subtitle" style={{ marginTop: 0 }}>
              {t.rankMyPreferences.dragHint}
            </p>

            <ol className={styles.rankList} data-tour="rank-list">
              {preferences.map((p, i) => {
                const cutoff = cutoffSummary(p.specialty, p.regionKey, p.institution);
                const key = comboKey(p.specialty, p.regionKey, p.institution || '');
                const isRegionOnly = !p.institution;
                const regionInstitutions = isRegionOnly
                  ? institutionsByCombo.get(baseComboKey(p.specialty, p.regionKey)) || []
                  : [];
                const canBreakdown = isRegionOnly && regionInstitutions.length > 0;
                // Single-institution region: reuse the likelihood panel's pct instead of a fresh, noisier simulation.
                const likelihoodPct =
                  regionInstitutions.length === 1
                    ? likelihood?.perOption.find(
                        (opt) => opt.specialty === p.specialty && opt.regionKey === p.regionKey && !opt.institution
                      )
                    : null;
                const breakdown = canBreakdown
                  ? institutionBreakdown(p.specialty, p.regionKey).map((inst) =>
                      likelihoodPct?.hasData ? { ...inst, pct: likelihoodPct.pct } : inst
                    )
                  : null;
                return (
                  <li key={key} className={styles.rankListItemWrap}>
                    <div
                      className={[styles.rankItem, dragOverIndex === i ? styles.rankItemDragOver : '']
                        .filter(Boolean)
                        .join(' ')}
                      draggable
                      onDragStart={() => handleDragStart(i)}
                      onDragOver={(e) => handleDragOver(i, e)}
                      onDrop={() => handleDrop(i)}
                      onDragEnd={() => setDragOverIndex(null)}
                      style={{ borderLeft: `3px solid ${colorForRegion(p.regionKey)}` }}
                    >
                      <span className={styles.rankItemLabel}>
                        <span className={styles.rankNumber}>{i + 1}.</span>{' '}
                        <span className={styles.comboItemTitle}>
                          {p.specialty} - {regionLabel(p.regionKey)}
                          {p.institution ? ` - ${p.institution}` : ''}
                        </span>
                        {cutoff && <span className={styles.cutoffTag}>{t.rankMyPreferences.lastCutoffs} {cutoff}</span>}
                      </span>
                      <span className={styles.rankControls}>
                        <button type="button" onClick={() => movePreference(i, -1)} aria-label={t.rankMyPreferences.moveUp} disabled={i === 0}>&uarr;</button>
                        <button type="button" onClick={() => movePreference(i, 1)} aria-label={t.rankMyPreferences.moveDown} disabled={i === preferences.length - 1}>&darr;</button>
                        <button type="button" onClick={() => removePreference(i)} aria-label={t.rankMyPreferences.remove}>&times;</button>
                      </span>
                    </div>
                    {canBreakdown && (
                      <div className={styles.institutionList}>
                        {breakdown.map((inst) => (
                          <div key={inst.institution} className={styles.institutionItem} style={{ cursor: 'default' }}>
                            <span className={styles.comboItemTitle}>{inst.institution}</span>
                            <span className={styles.comboItemMeta}>
                              {inst.seats} {t.rankMyPreferences.seats}
                              {inst.cutoffText && (
                                <span className={styles.cutoffTag}> · {t.rankMyPreferences.lastCutoffs} {inst.cutoffText}</span>
                              )}
                              {inst.pct !== null && (
                                <span className={styles.cutoffTag} style={{ color: colorForPct(inst.pct) }}>
                                  {t.rankMyPreferences.chanceOfEntering(inst.pct)}
                                </span>
                              )}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
              {preferences.length === 0 && (
                <p className="subtitle">{t.rankMyPreferences.nothingSketched}</p>
              )}
            </ol>
          </div>
        </div>

        {likelihood && likelihood.noDataAtAll && (
          <p className="subtitle">
            {t.rankMyPreferences.noDataAtAll}
          </p>
        )}

        {likelihood && !likelihood.noDataAtAll && (
          <div className={styles.likelihoodPanel} data-tour="rank-likelihood">
            <h4 className={styles.subheading} style={{ marginBottom: '0.35rem' }}>
              {t.rankMyPreferences.likelihoodHeading(LIKELIHOOD_TRIALS, myNumber, clampedOffset)}
              <span className={styles.infoIcon} tabIndex={0} role="note" aria-label={t.rankMyPreferences.likelihoodTooltipLabel}>
                i
                <span className={styles.infoTooltip}>
                  {t.rankMyPreferences.likelihoodTooltip(LIKELIHOOD_TRIALS, clampedOffset)}
                </span>
              </span>
            </h4>
            <ul className={styles.likelihoodList}>
              {likelihood.perOption.map((opt, i) => {
                const key = comboKey(opt.specialty, opt.regionKey, opt.institution || '');
                const regionInstitutions = !opt.institution
                  ? institutionsByCombo.get(baseComboKey(opt.specialty, opt.regionKey)) || []
                  : [];
                const canBreakdown = !opt.institution && regionInstitutions.length > 0;
                // A single-institution region *is* that institution -- reuse its pct rather than re-simulating.
                const breakdown = canBreakdown
                  ? institutionBreakdown(opt.specialty, opt.regionKey).map(
                      (inst) => (regionInstitutions.length === 1 && opt.hasData ? { ...inst, pct: opt.pct } : inst)
                    )
                  : null;
                return (
                  <li key={key} className={styles.rankListItemWrap}>
                    <div
                      className={styles.likelihoodItem}
                      style={{ borderLeft: `3px solid ${colorForRegion(opt.regionKey)}` }}
                    >
                      <span className={styles.likelihoodLabel}>
                        {i + 1}. {opt.specialty} - {regionLabel(opt.regionKey)}
                        {opt.institution ? ` - ${opt.institution}` : ''}
                        {!opt.hasData && <span className={styles.cutoffTag}> {t.rankMyPreferences.noHistoricalData}</span>}
                      </span>
                      <span className={styles.likelihoodBarTrack}>
                        <span
                          className={styles.likelihoodBarFill}
                          style={{ width: `${opt.pct}%`, background: colorForPct(opt.pct) }}
                        />
                      </span>
                      <span className={styles.likelihoodPct} style={{ color: opt.hasData ? colorForPct(opt.pct) : undefined }}>
                        {opt.hasData ? `${opt.pct}%` : '-'}
                      </span>
                    </div>
                    {canBreakdown && (
                      <div className={styles.institutionList}>
                        {breakdown.map((inst) => (
                          <div key={inst.institution} className={styles.institutionItem} style={{ cursor: 'default' }}>
                            <span className={styles.comboItemTitle}>{inst.institution}</span>
                            <span className={styles.comboItemMeta}>
                              {inst.seats} {t.rankMyPreferences.seats}
                              {inst.cutoffText && (
                                <span className={styles.cutoffTag}> · {t.rankMyPreferences.lastCutoffs} {inst.cutoffText}</span>
                              )}
                              {inst.pct !== null && (
                                <span className={styles.cutoffTag} style={{ color: colorForPct(inst.pct) }}>
                                  {t.rankMyPreferences.chanceOfEntering(inst.pct)}
                                </span>
                              )}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="subtitle" style={{ marginTop: '0.4rem' }}>
              {t.rankMyPreferences.notPlaced(likelihood.notPlacedPct)}
            </p>
          </div>
        )}
      </div>
    </>
  );
};

export default RankMyPreferences;
