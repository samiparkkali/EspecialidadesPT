import SearchableSelect from '../SearchableSelect/SearchableSelect';
import { useLanguage } from '../../i18n/LanguageContext';

const Filters = ({ specialties, institutions, specialty, institution, onSpecialtyChange, onInstitutionChange }) => {
  const { t } = useLanguage();
  return (
    <div className="card filters-row" data-tour="filters">
      <SearchableSelect
        label={t.filters.specialty}
        options={specialties}
        value={specialty}
        onChange={onSpecialtyChange}
      />
      <SearchableSelect
        label={t.filters.institution}
        options={institutions}
        value={institution}
        onChange={onInstitutionChange}
      />
    </div>
  );
};

export default Filters;
