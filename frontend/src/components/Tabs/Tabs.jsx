import { useEffect, useRef, useState } from 'react';
import styles from './Tabs.module.css';

const Tabs = ({ tabs, active, onChange, onStuckChange }) => {
  const sentinelRef = useRef(null);
  const [stuck, setStuck] = useState(false);

  // A 0-height sentinel right before the sticky bar: once it scrolls out of view, the bar is pinned, so add the floating style.
  // onStuckChange lets a sibling outside this component (the fixed top-left
  // language toggle) react to the same transition -- once the full-bleed bar
  // is pinned, its leftmost tab sits right under that toggle's corner spot.
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      setStuck(!entry.isIntersecting);
      onStuckChange?.(!entry.isIntersecting);
    }, {
      threshold: 0,
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [onStuckChange]);

  return (
    <>
      <div ref={sentinelRef} />
      <div data-tour="tabs" className={stuck ? `${styles.tabs} ${styles.stuck}` : styles.tabs}>
        <div className={styles.tabsInner}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={active === tab.id ? styles.tabActive : styles.tab}
              onClick={() => onChange(tab.id)}
            >
              <span className={styles.labelFull}>{tab.label}</span>
              <span className={styles.labelShort}>{tab.shortLabel || tab.label}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
};

export default Tabs;
