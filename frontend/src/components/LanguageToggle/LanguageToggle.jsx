import { useLanguage } from '../../i18n/LanguageContext';
import styles from './LanguageToggle.module.css';

const LanguageToggle = () => {
  const { language, setLanguage, t } = useLanguage();

  return (
    <div className={styles.toggle} role="group" aria-label={t.languageToggle.groupLabel}>
      <button
        type="button"
        className={language === 'pt' ? styles.active : styles.button}
        onClick={() => setLanguage('pt')}
        aria-pressed={language === 'pt'}
      >
        PT
      </button>
      <span aria-hidden="true" className={styles.divider}>|</span>
      <button
        type="button"
        className={language === 'en' ? styles.active : styles.button}
        onClick={() => setLanguage('en')}
        aria-pressed={language === 'en'}
      >
        EN
      </button>
    </div>
  );
};

export default LanguageToggle;
