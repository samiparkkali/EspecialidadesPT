import { useEffect, useState } from 'react';

// Loads the static JSON exported from data/processed/*.csv (see
// backend/extract_vagas.py, backend/extract_colocados.py, and the export
// step in the Makefile). No backend call -- this is what keeps the site
// deployable as a static GitHub Pages build.
export const useDataset = (filename) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${import.meta.env.BASE_URL}data/${filename}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${filename}: ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [filename]);

  return { data, error, loading: data === null && error === null };
};
