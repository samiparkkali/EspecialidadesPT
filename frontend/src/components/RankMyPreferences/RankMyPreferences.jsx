import { useMemo, useRef, useState } from 'react';
import SearchableSelect from '../SearchableSelect/SearchableSelect';
import { colorForRegion } from '../../utils/regionColors';
import styles from './RankMyPreferences.module.css';

const LIKELIHOOD_TRIALS = 1000;

const REGION_LABELS = {
  norte: 'NORTE',
  centro: 'CENTRO',
  'lisboa-vale-tejo': 'LVT',
  alentejo: 'ALENTEJO',
  algarve: 'ALGARVE',
  acores: 'AÇORES',
  madeira: 'MADEIRA',
};

// Green (likely to enter) -> yellow -> red (unlikely), for likelihood pct display.
const colorForPct = (pct) => {
  const p = Math.max(0, Math.min(100, pct));
  const hue = (p / 100) * 120; // 0 = red, 120 = green
  return `hsl(${hue}, 70%, 42%)`;
};

const regionLabel = (regionKey) =>
  REGION_LABELS[regionKey] || (regionKey ? regionKey.replace(/-/g, ' ').toUpperCase() : 'UNMAPPED REGION');

// Institution '' means "the whole region aggregate", not a specific hospital.
const comboKey = (specialty, regionKey, institution = '') => `${specialty}|||${regionKey}|||${institution}`;
const baseComboKey = (specialty, regionKey) => `${specialty}|||${regionKey}`;
const cutoffKey = (specialty, institution) => `${specialty}|||${institution}`;

// Weighted random pick -- used to pick which institution a region-only
// preference "means" for a trial, bigger institutions more likely.
const pickWeighted = (items, weightFn) => {
  const total = items.reduce((sum, item) => sum + weightFn(item), 0);
  let r = Math.random() * total;
  for (const item of items) {
    r -= weightFn(item);
    if (r <= 0) return item;
  }
  return items[items.length - 1];
};

// Draws one plausible cutoff from an option's own historical years, rather
// than assuming every year wants the same ranking (that used to make popular
// first choices look impossible). Region-only: weight-picks an institution
// by seats first, then samples its history. null means no historical data.
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

// Each option's pct is its own MARGINAL odds of admitting your drawn number,
// independent of other options -- so a safe low-cutoff option near the
// bottom still shows near-100% even though you'd likely be placed earlier.
// That "placed earlier" effect is summarized once in notPlacedPct instead.
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

const RankMyPreferences = ({ vagas, colocados }) => {
  const [preferences, setPreferences] = useState([]);
  const [expandedCombo, setExpandedCombo] = useState(null);
  const [myOrderingNumber, setMyOrderingNumber] = useState('');
  const [spreadOffset, setSpreadOffset] = useState(200);
  const [comboFilter, setComboFilter] = useState('');
  const [specialtyFilter, setSpecialtyFilter] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
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

  // Region lookup from ALL years of vagas (not just latestYear) so an
  // institution that has cutoff history but no seat this year can still be
  // placed under its right region below, instead of vanishing.
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

    // Union in institutions with colocados cutoff history that have no seat
    // this year (renamed, merged, or simply not offered) -- otherwise their
    // history is invisible here even though Predict shows it fine, since
    // Predict reads all years of colocados directly with no seat filter.
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

  // Historical "Golden Ticket Number" cutoffs per specialty+institution, every
  // year on record, most recent first -- context for "is this realistic for
  // my number" and the raw material the likelihood panel samples from.
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

  // Region entries show a range across institutions (which can straddle very
  // different cutoffs) rather than one specific institution's history.
  const cutoffSummary = (specialty, regionKey, institution) => {
    if (institution) {
      const entries = cutoffsByKey.get(cutoffKey(specialty, institution));
      if (!entries || entries.length === 0) return null;
      return entries.map(([year, n]) => `${year}: ${n}`).join(' · ');
    }
    const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
    // A single-institution region has no "range across institutions" to
    // summarize -- show its full multi-year history instead of collapsing
    // to just the latest year.
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

  // Cache per (specialty, region) for the current inputs, since this render
  // pass's "Your ranking" and "Likelihood" panels both compute the breakdown
  // for the same region-only preference -- without caching, each call rolled
  // its own fresh Math.random() trials, so the same institution could show
  // two different percentages on screen at once (and flicker on any
  // unrelated re-render).
  const breakdownCache = useMemo(() => new Map(), [myNumber, clampedOffset, institutionsByCombo, cutoffsByKey, maxOrdering]);

  const institutionBreakdown = (specialty, regionKey, myNum, offset, maxOrd) => {
    const cacheKey = `${specialty}|||${regionKey}`;
    if (breakdownCache.has(cacheKey)) return breakdownCache.get(cacheKey);
    const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
    const result = institutions.map((inst) => {
      const entries = cutoffsByKey.get(cutoffKey(specialty, inst.institution));
      const cutoffText = entries && entries.length ? entries.map(([year, n]) => `${year}: ${n}`).join(' · ') : null;
      let pct = null;
      if (myNum && entries && entries.length) {
        let hits = 0;
        for (let t = 0; t < LIKELIHOOD_TRIALS; t++) {
          const drawnNumber = Math.min(maxOrd, Math.max(1, myNum + Math.round((Math.random() * 2 - 1) * offset)));
          const cutoff = entries[Math.floor(Math.random() * entries.length)][1];
          if (drawnNumber <= cutoff) hits += 1;
        }
        pct = Math.round((hits / LIKELIHOOD_TRIALS) * 100);
      }
      return { institution: inst.institution, seats: inst.seats, cutoffText, pct };
    });
    breakdownCache.set(cacheKey, result);
    return result;
  };

  const availableCombos = useMemo(() => {
    const combos = [];
    for (const specialty of allSpecialties) {
      for (const regionKey of allRegions) {
        const seats = seatsByCombo.get(comboKey(specialty, regionKey)) || 0;
        const institutions = institutionsByCombo.get(baseComboKey(specialty, regionKey)) || [];
        // Keep a combo browsable even with 0 current seats, as long as some
        // institution in it has real cutoff history (see institutionsByCombo).
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
      if (specialtyFilter && c.specialty !== specialtyFilter) return false;
      if (regionFilter && c.regionKey !== regionFilter) return false;
      if (!q) return true;
      return c.specialty.toLowerCase().includes(q) || regionLabel(c.regionKey).toLowerCase().includes(q);
    });
  }, [availableCombos, comboFilter, specialtyFilter, regionFilter]);

  const maxOrdering = useMemo(() => {
    const numbers = colocados.map((r) => Number(r.ordering_number)).filter((n) => n > 0);
    return numbers.length ? Math.max(...numbers) : 3000;
  }, [colocados]);

  // A combo is ranked as a whole region OR split into institutions, never
  // both -- the region total already includes every institution's seats.
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

  if (!latestYear) {
    return (
      <div className="card">
        <p className="subtitle">
          No institution-level seat data loaded yet, so preferences can&apos;t be built.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <h2>Rank My Preferences</h2>
        <p className="subtitle">
          A sketchboard for thinking through your "ordem de colocação" (Golden Ticket Number) choices. Browse
          specialty/region/institution options on the left, click to add them to your ranking on the right, and
          freely reorder or remove anything as you think it through: there&apos;s no required minimum. Seats and
          recent Golden Ticket Number cutoffs from {latestYear} and prior years are shown next to each option so you
          can judge how realistic a spot is for your own number.
        </p>

        <div className={styles.filterRow}>
          <SearchableSelect
            label="Specialty"
            options={allSpecialties}
            value={specialtyFilter}
            onChange={setSpecialtyFilter}
            placeholder="Filter specialty..."
          />
          <SearchableSelect
            label="Region"
            options={allRegions}
            value={regionFilter}
            onChange={(v) => setRegionFilter(v)}
            placeholder="Filter region..."
            getLabel={regionLabel}
          />
          <label className={styles.textFilter}>
            Search
            <input
              type="text"
              placeholder="Specialty or region..."
              value={comboFilter}
              onChange={(e) => setComboFilter(e.target.value)}
            />
          </label>
        </div>

        <div className={styles.rankLayout}>
          <div>
            <h3 className={styles.subheading}>
              Browse options ({filteredCombos.length})
            </h3>
            <div className={styles.comboList}>
              {filteredCombos.map((combo) => {
                const base = baseComboKey(combo.specialty, combo.regionKey);
                // Show the expand arrow even for a single institution -- a
                // region with just one hospital still means one specific
                // place, and hiding its name behind the region label alone
                // was confusing (e.g. "Anestesiologia - Açores").
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
                        onClick={() => addPreference(combo.specialty, combo.regionKey)}
                        disabled={anyEntryUsed}
                      >
                        <span className={styles.comboItemTitle}>
                          {combo.specialty} - {regionLabel(combo.regionKey)}
                        </span>
                        <span className={styles.comboItemMeta}>
                          {combo.seats} seats
                          {regionCutoff && (
                            <span className={styles.cutoffTag}> · last cutoffs {regionCutoff}</span>
                          )}
                        </span>
                      </button>
                      {hasMultipleInstitutions && (
                        <button
                          type="button"
                          className={styles.expandButton}
                          onClick={() => setExpandedCombo(expandedCombo === base ? null : base)}
                          aria-label="Show institutions"
                        >
                          {expandedCombo === base ? '▾' : '▸'} institutions
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
                              disabled={regionUsed || used}
                              onClick={() => addPreference(combo.specialty, combo.regionKey, inst.institution)}
                            >
                              <span className={styles.comboItemTitle}>{inst.institution}</span>
                              <span className={styles.comboItemMeta}>
                                {inst.seats} seats
                                {instCutoff && <span className={styles.cutoffTag}> · last cutoffs {instCutoff}</span>}
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
                <p className="subtitle">No combos match the current filters.</p>
              )}
            </div>

            <div className={styles.numberRow}>
              <label>
                Your Golden Ticket Number
                <input
                  type="number"
                  min="1"
                  required
                  placeholder="e.g. 1240"
                  value={myOrderingNumber}
                  onChange={(e) => setMyOrderingNumber(e.target.value)}
                />
              </label>
              <label>
                Spread around your number (&plusmn;)
                <input
                  type="number"
                  min="1"
                  value={spreadOffset}
                  onChange={(e) => setSpreadOffset(Math.max(1, Number(e.target.value) || 200))}
                />
              </label>
            </div>
            <p className="subtitle" style={{ marginTop: 0 }}>
              Your final Golden Ticket Number always carries some uncertainty. The spread sets how far off it could
              realistically land, and the likelihood panel below draws a random number within that range on every
              trial, so a wider spread means more variability (and less certainty) in the odds shown.
            </p>
            {!myNumber && (
              <p className="subtitle">
                Enter your Golden Ticket Number to see your odds of entering each option ranked below.
              </p>
            )}
          </div>
          <div>
            <h3 className={styles.subheading}>Your ranking ({preferences.length})</h3>
            <p className="subtitle" style={{ marginTop: 0 }}>
              Drag to reorder, or use the arrows. This is your working sketch: add, remove and reshuffle freely.
            </p>

            <ol className={styles.rankList}>
              {preferences.map((p, i) => {
                const cutoff = cutoffSummary(p.specialty, p.regionKey, p.institution);
                const key = comboKey(p.specialty, p.regionKey, p.institution || '');
                const isRegionOnly = !p.institution;
                const regionInstitutions = isRegionOnly
                  ? institutionsByCombo.get(baseComboKey(p.specialty, p.regionKey)) || []
                  : [];
                const canBreakdown = isRegionOnly && regionInstitutions.length > 0;
                const breakdown = canBreakdown
                  ? institutionBreakdown(p.specialty, p.regionKey, myNumber, clampedOffset, maxOrdering)
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
                        {cutoff && <span className={styles.cutoffTag}>last cutoffs {cutoff}</span>}
                      </span>
                      <span className={styles.rankControls}>
                        <button type="button" onClick={() => movePreference(i, -1)} aria-label="Move up" disabled={i === 0}>&uarr;</button>
                        <button type="button" onClick={() => movePreference(i, 1)} aria-label="Move down" disabled={i === preferences.length - 1}>&darr;</button>
                        <button type="button" onClick={() => removePreference(i)} aria-label="Remove">&times;</button>
                      </span>
                    </div>
                    {canBreakdown && (
                      <div className={styles.institutionList}>
                        {breakdown.map((inst) => (
                          <div key={inst.institution} className={styles.institutionItem} style={{ cursor: 'default' }}>
                            <span className={styles.comboItemTitle}>{inst.institution}</span>
                            <span className={styles.comboItemMeta}>
                              {inst.seats} seats
                              {inst.cutoffText && (
                                <span className={styles.cutoffTag}> · last cutoffs {inst.cutoffText}</span>
                              )}
                              {inst.pct !== null && (
                                <span className={styles.cutoffTag} style={{ color: colorForPct(inst.pct) }}>
                                  {' '}
                                  · ~{inst.pct}% chance of entering
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
                <p className="subtitle">Nothing sketched yet. Click an option on the left to start.</p>
              )}
            </ol>
          </div>
        </div>

        {likelihood && likelihood.noDataAtAll && (
          <p className="subtitle">
            None of your ranked options have any historical Golden Ticket Number data to estimate odds from.
          </p>
        )}

        {likelihood && !likelihood.noDataAtAll && (
          <div className={styles.likelihoodPanel}>
            <h4 className={styles.subheading} style={{ marginBottom: '0.35rem' }}>
              Likelihood of entering each option ({LIKELIHOOD_TRIALS} trials, your number {myNumber} &plusmn;{' '}
              {clampedOffset}, cutoffs sampled from each option&apos;s own year-to-year history)
            </h4>
            <ul className={styles.likelihoodList}>
              {likelihood.perOption.map((opt, i) => {
                const key = comboKey(opt.specialty, opt.regionKey, opt.institution || '');
                const regionInstitutions = !opt.institution
                  ? institutionsByCombo.get(baseComboKey(opt.specialty, opt.regionKey)) || []
                  : [];
                const canBreakdown = !opt.institution && regionInstitutions.length > 0;
                const breakdown = canBreakdown
                  ? institutionBreakdown(opt.specialty, opt.regionKey, myNumber, clampedOffset, maxOrdering)
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
                        {!opt.hasData && <span className={styles.cutoffTag}> no historical data</span>}
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
                              {inst.seats} seats
                              {inst.cutoffText && (
                                <span className={styles.cutoffTag}> · last cutoffs {inst.cutoffText}</span>
                              )}
                              {inst.pct !== null && (
                                <span className={styles.cutoffTag} style={{ color: colorForPct(inst.pct) }}>
                                  {' '}
                                  · ~{inst.pct}% chance of entering
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
              Not placed by any ranked option (with data): {likelihood.notPlacedPct}% of draws.
            </p>
          </div>
        )}
      </div>
    </>
  );
};

export default RankMyPreferences;
