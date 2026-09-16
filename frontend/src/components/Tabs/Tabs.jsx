import styles from './Tabs.module.css';

const Tabs = ({ tabs, active, onChange }) => (
  <div className={styles.tabs}>
    {tabs.map((tab) => (
      <button
        key={tab.id}
        type="button"
        className={active === tab.id ? styles.tabActive : styles.tab}
        onClick={() => onChange(tab.id)}
      >
        {tab.label}
      </button>
    ))}
  </div>
);

export default Tabs;
