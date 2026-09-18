import { demoFillSearch, demoAddPreference, demoFillNumber } from './rankDemo';

// One entry per stop. `demo`, when present, runs a live example against the real page (Rank My Preferences steps).
export const TOUR_STEPS = [
  {
    tab: 'overview',
    selector: '[data-tour="tabs"]',
    title: 'Switch between views',
    text: "These tabs switch between ways to explore the data: yearly trends, this year's seats, per-specialty stats, and a preference-ranking sketchboard.",
  },
  {
    tab: 'overview',
    selector: '[data-tour="filters"]',
    title: 'Filter by specialty and institution',
    text: 'Narrow everything below to one specialty and/or institution. Leave either empty to see totals across all of them.',
  },
  {
    tab: 'overview',
    selector: '[data-tour="evolution-chart"]',
    title: 'See the seats trend over time',
    text: "This chart shows how many seats were offered each year for your current filters, plus a simple trend projection for next year (marked with *).",
  },
  {
    tab: 'overview',
    selector: '[data-tour="predict"]',
    title: 'Check your Golden Ticket Number',
    text: "Enter your ordering number (\"ordem de colocação\") to see which specialty/institution combinations it would have gotten you into, checked separately against each past year's cutoff.",
  },
  {
    tab: 'this-year',
    selector: '[data-tour="portugal-map"]',
    title: "Explore this year's seats by region",
    text: 'Click a region on the map to filter the specialty breakdown below to just that region.',
  },
  {
    tab: 'specialty-stats',
    selector: '[data-tour="specialty-stats"]',
    title: 'Dig into one specialty',
    text: "Pick any specialty to see its seat count over the years, plus how that count splits across regions and institutions.",
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-preferences"]',
    title: 'Sketch your preference ranking',
    text: "A sandbox for thinking through your \"ordem de colocação\" choices before submitting them for real.",
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-filters"]',
    title: 'Narrow down the options',
    text: 'Filter the browsable list by specialty, region, or free-text search to find what you want to rank faster.',
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-browse"]',
    title: 'Add options to your ranking',
    demo: demoFillSearch,
    text: 'Click a specialty/region combo to add it, or expand it to pick a specific institution instead. We just typed "Cirurgia Geral" into the search box above, filtering this list down to just its combos.',
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-number"]',
    title: 'Enter your Golden Ticket Number',
    demo: demoFillNumber,
    text: 'We filled in an example number, 1500, with a spread of +/-200. Your real ordering number plus how uncertain it might land drives the odds shown for every ranked option below.',
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-list"]',
    title: 'Watch it land in your scratchpad',
    demo: demoAddPreference,
    text: 'Clicking a combo (like the Cirurgia Geral one just filtered) adds it here immediately, as you can see. From here you can drag to reorder, use the arrows, or remove it: nothing is final.',
  },
  {
    tab: 'rank-preferences',
    selector: '[data-tour="rank-likelihood"]',
    title: 'See the Monte Carlo simulation run',
    text: 'With a number and a ranked option, this panel now shows live simulated odds for the Cirurgia Geral entry we just added. Hover the (i) icon on the heading for exactly how the percentages are computed.',
  },
];
