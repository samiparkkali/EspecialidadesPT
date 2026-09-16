import SearchableSelect from '../SearchableSelect/SearchableSelect';

const Filters = ({ specialties, institutions, specialty, institution, onSpecialtyChange, onInstitutionChange }) => (
  <div className="card filters-row">
    <SearchableSelect
      label="Specialty"
      options={specialties}
      value={specialty}
      onChange={onSpecialtyChange}
    />
    <SearchableSelect
      label="Institution"
      options={institutions}
      value={institution}
      onChange={onInstitutionChange}
    />
  </div>
);

export default Filters;
