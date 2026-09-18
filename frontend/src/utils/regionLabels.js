// Display label per health region, shared by every view that filters or
// groups by region_key.
const REGION_LABELS = {
  norte: 'NORTE',
  centro: 'CENTRO',
  'lisboa-vale-tejo': 'LVT',
  alentejo: 'ALENTEJO',
  algarve: 'ALGARVE',
  acores: 'AÇORES',
  madeira: 'MADEIRA',
};

export const regionLabel = (regionKey) =>
  REGION_LABELS[regionKey] || (regionKey ? regionKey.replace(/-/g, ' ').toUpperCase() : 'UNMAPPED REGION');
