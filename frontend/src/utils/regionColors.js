// One fixed color per health region, shared by the map and every chart --
// keyed by region_key so a region is always the same color everywhere,
// regardless of which subset of regions a given view happens to show.
const REGION_COLOR_VAR = {
  norte: '--region-norte',
  centro: '--region-centro',
  'lisboa-vale-tejo': '--region-lisboa-vale-tejo',
  alentejo: '--region-alentejo',
  algarve: '--region-algarve',
  acores: '--region-acores',
  madeira: '--region-madeira',
};

export const colorForRegion = (regionKey) => `var(${REGION_COLOR_VAR[regionKey] || '--color-text-muted'})`;
