import { useMemo, useState } from 'react';
import SearchableSelect from '../SearchableSelect/SearchableSelect';

// Mirrors backend/api.py's /api/predict: for each specialty/institution,
// track the "last ordering number placed" (the cutoff) per year in
// colocados.json. A candidate with a given ordering number would have
// gotten in for any year where their number is <= that year's cutoff
// (lower ordering number = better rank). Shown per-year, plus an average,
// since a single averaged cutoff hides how much it varies year to year --
// this gets more accurate as more years' colocados data get added.
const buildCutoffsByYear = (colocados) => {
  const grouped = new Map();
  for (const row of colocados) {
    const key = `${row.specialty}|||${row.canonical_institution || row.institution}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        specialty: row.specialty,
        institution: row.canonical_institution || row.institution,
        cutoffByYear: new Map(),
      });
    }
    const entry = grouped.get(key);
    const year = Number(row.year);
    const ordering = Number(row.ordering_number);
    entry.cutoffByYear.set(year, Math.max(entry.cutoffByYear.get(year) || 0, ordering));
  }
  return Array.from(grouped.values());
};

const Predict = ({ colocados }) => {
  const [orderingNumber, setOrderingNumber] = useState('');
  const [specialtyFilter, setSpecialtyFilter] = useState('');
  const groups = useMemo(() => buildCutoffsByYear(colocados), [colocados]);

  const specialties = useMemo(
    () => [...new Set(groups.map((g) => g.specialty))].sort(),
    [groups]
  );

  const results = useMemo(() => {
    const n = Number(orderingNumber);
    if (!orderingNumber || Number.isNaN(n) || n <= 0) return null;

    return groups
      .filter((g) => !specialtyFilter || g.specialty === specialtyFilter)
      .map((g) => {
        const years = Array.from(g.cutoffByYear.entries());
        const eligibleYears = years.filter(([, cutoff]) => cutoff >= n).map(([year]) => year);
        const avgCutoff = Math.round(
          years.reduce((sum, [, c]) => sum + c, 0) / years.length
        );
        return {
          specialty: g.specialty,
          institution: g.institution,
          avgCutoff,
          eligibleYears: eligibleYears.sort((a, b) => a - b),
          totalYears: years.length,
        };
      })
      .filter((r) => r.eligibleYears.length > 0)
      .sort((a, b) => b.eligibleYears.length - a.eligibleYears.length || a.avgCutoff - b.avgCutoff);
  }, [groups, orderingNumber, specialtyFilter]);

  return (
    <div className="card">
      <h2>O que posso escolher com o meu número de ordenação?</h2>
      <p className="subtitle">
        Para cada especialidade/instituição, mostra em que anos o número de
        ordenação introduzido teria entrado (número de ordenação ≤ último
        colocado nesse ano). Não é uma previsão real do próximo ano — apenas
        o que os dados já carregados mostram, ano a ano.
      </p>
      <div className="filters-row">
        <label htmlFor="ordering-input">
          Número de ordenação
          <input
            id="ordering-input"
            type="number"
            min="1"
            value={orderingNumber}
            onChange={(e) => setOrderingNumber(e.target.value)}
            placeholder="Ex: 1200"
          />
        </label>

        <SearchableSelect
          label="Especialidade"
          options={specialties}
          value={specialtyFilter}
          onChange={setSpecialtyFilter}
        />
      </div>

      {results && (
        <table style={{ marginTop: '1rem' }}>
          <thead>
            <tr>
              <th>Especialidade</th>
              <th>Instituição</th>
              <th>Anos em que entraria</th>
              <th>Cutoff médio</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={`${r.specialty}|${r.institution}`}>
                <td>{r.specialty}</td>
                <td>{r.institution}</td>
                <td>
                  {r.eligibleYears.join(', ')}
                  {r.eligibleYears.length < r.totalYears && (
                    <span className="subtitle"> (de {r.totalYears} anos com dados)</span>
                  )}
                </td>
                <td>{r.avgCutoff}</td>
              </tr>
            ))}
            {results.length === 0 && (
              <tr>
                <td colSpan={4}>Nenhuma opção encontrada para este número, com os dados atuais.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default Predict;
