import { useEffect, useState } from 'react';
import { LanguageContext } from './LanguageContext';
import { translations } from './translations';

const STORAGE_KEY = 'internato-language';

function getInitialLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'pt' || stored === 'en') return stored;
  } catch {
    // localStorage unavailable (private browsing, etc.) -- default stands
  }
  return 'pt';
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(getInitialLanguage);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = (lang) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // ignore -- nothing to persist to
    }
  };

  const value = { language, setLanguage, t: translations[language] };

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
