import { demoFillSearch, demoAddPreference, demoFillNumber } from './rankDemo';

// Non-text fields (tab, selector, demo) per stop, in the same order as `t.tour.steps`
// (translations.js) -- built into full step objects by buildTourSteps below. `demo`,
// when present, runs a live example against the real page (Rank My Preferences steps).
const STEP_META = [
  { tab: 'overview', selector: '[data-tour="tabs"]' },
  { tab: 'overview', selector: '[data-tour="filters"]' },
  { tab: 'overview', selector: '[data-tour="evolution-chart"]' },
  { tab: 'overview', selector: '[data-tour="predict"]' },
  { tab: 'this-year', selector: '[data-tour="portugal-map"]' },
  { tab: 'specialty-stats', selector: '[data-tour="specialty-stats"]' },
  { tab: 'rank-preferences', selector: '[data-tour="rank-preferences"]' },
  { tab: 'rank-preferences', selector: '[data-tour="rank-filters"]' },
  { tab: 'rank-preferences', selector: '[data-tour="rank-browse"]', demo: demoFillSearch },
  { tab: 'rank-preferences', selector: '[data-tour="rank-number"]', demo: demoFillNumber },
  { tab: 'rank-preferences', selector: '[data-tour="rank-browse"]', demo: demoAddPreference },
  { tab: 'rank-preferences', selector: '[data-tour="rank-likelihood"]' },
];

// Merges the language-specific title/text (from translations.js's `t.tour.steps`) with
// the fixed non-text fields above, so the tour stays in one place per language.
export const buildTourSteps = (t) =>
  STEP_META.map((meta, i) => ({
    ...meta,
    title: t.tour.steps[i].title,
    text: t.tour.steps[i].text,
  }));
