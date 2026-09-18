import { useEffect, useRef, useState } from 'react';
import styles from './Tabs.module.css';

const Tabs = ({ tabs, active, onChange }) => {
  const sentinelRef = useRef(null);
  const [stuck, setStuck] = useState(false);

  // A 0-height sentinel placed right before the sticky bar: once it scrolls
  // out of view, the bar itself must be pinned to the top, so that's the cue
  // to add the "floating" shadow/background.
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return undefined;
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), {
      threshold: 0,
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

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
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </>
  );
};

export default Tabs;
