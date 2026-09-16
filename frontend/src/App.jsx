import { useMemo, useState } from 'react';
import { useDataset } from './hooks/useDataset';
import Filters from './components/Filters/Filters';
import Evolution from './components/Evolution/Evolution';
import Predict from './components/Predict/Predict';

function App() {
  const { data: vagas, error: vagasError } = useDataset('vagas.json');
  const { data: colocados, error: colocadosError } = useDataset('colocados.json');

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
        .map((r) => r.canonical_institution || r.institution)
        .filter(Boolean)
    )].sort();
  }, [vagas]);

  const evolutionPoints = useMemo(() => {
    if (!vagas) return [];
    const rows = vagas.filter((r) => r.institution);
    const filtered = rows.filter((r) => {
      if (specialty && r.specialty !== specialty) return false;
      if (institution && (r.canonical_institution || r.institution) !== institution) return false;
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
    return <p>Erro a carregar os dados: {String(vagasError || colocadosError)}</p>;
  }

  if (!vagas || !colocados) {
    return <p>A carregar dados...</p>;
  }

  return (
    <>
      <h1>Grey&apos;s Internato</h1>
      <p className="subtitle">
        It&apos;s a beautiful day to pick the specialty that will one day let
        you retire early and become a happy plumber. Evolução de vagas do
        Internato Médico por especialidade, instituição e ano. Dados
        extraídos dos avisos oficiais da ACSS.
      </p>

      <Filters
        specialties={specialties}
        institutions={institutions}
        specialty={specialty}
        institution={institution}
        onSpecialtyChange={setSpecialty}
        onInstitutionChange={setInstitution}
      />

      <Evolution points={evolutionPoints} />

      <Predict colocados={colocados} />
    </>
  );
}

export default App;
