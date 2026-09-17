import styles from './Spinner.module.css';

// `size="small"` for an inline spinner next to/inside existing content
// (e.g. a list that's mid-refresh); the default fills its container, for a
// page/tab that has nothing else to show yet.
const Spinner = ({ label = 'Loading...', size = 'default' }) => (
  <div className={`${styles.wrap} ${size === 'small' ? styles.small : ''}`} role="status" aria-live="polite">
    <span className={styles.spinner} aria-hidden="true" />
    {label && <span className={styles.label}>{label}</span>}
  </div>
);

export default Spinner;
