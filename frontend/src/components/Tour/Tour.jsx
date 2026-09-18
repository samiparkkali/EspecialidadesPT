import { useEffect, useMemo, useState } from 'react';
import { TOUR_STEPS } from './tourSteps';
import { undoRankDemo } from './rankDemo';
import styles from './Tour.module.css';

const STORAGE_KEY = 'tour-seen';

// localStorage can throw (private mode, disabled storage) -- treat that as
// "already seen" so a broken read never re-nags the user every load.
const hasSeenTour = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return true;
  }
};

const markTourSeen = () => {
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // Storage unavailable -- the tour just re-prompts next visit, harmless.
  }
};

const MARGIN = 12;
const TOOLTIP_WIDTH = 320;
const TOOLTIP_HEIGHT_ESTIMATE = 170;

// Pure placement math from measured state only (never reads window.* live
// during render, so it stays stable across concurrent re-renders).
const placeTooltip = (rect, viewport) => {
  if (!rect || !viewport) {
    return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: `${TOOLTIP_WIDTH}px` };
  }
  const width = Math.min(TOOLTIP_WIDTH, viewport.width - MARGIN * 2);

  let top = rect.bottom + MARGIN;
  if (top + TOOLTIP_HEIGHT_ESTIMATE > viewport.height) {
    top = rect.top - MARGIN - TOOLTIP_HEIGHT_ESTIMATE;
  }
  top = Math.max(MARGIN, Math.min(top, viewport.height - TOOLTIP_HEIGHT_ESTIMATE - MARGIN));

  let left = rect.left + rect.width / 2 - width / 2;
  left = Math.max(MARGIN, Math.min(left, viewport.width - width - MARGIN));

  return { top: `${top}px`, left: `${left}px`, width: `${width}px` };
};

const Tour = ({ activeTab, onChangeTab }) => {
  const [phase, setPhase] = useState(() => (hasSeenTour() ? 'idle' : 'prompt'));
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const [viewport, setViewport] = useState(null);

  const step = phase === 'running' ? TOUR_STEPS[stepIndex] : null;

  // Only undoes when leaving the rank-preferences demo range entirely (a tab
  // switch, finish, or skip) -- stepping back and forth WITHIN it must leave
  // the demo's cumulative state alone, since later steps (the likelihood
  // panel) read what earlier ones built up rather than re-creating it.
  const goToStep = (index) => {
    if (index < 0 || index >= TOUR_STEPS.length) {
      if (TOUR_STEPS[stepIndex]?.tab === 'rank-preferences') undoRankDemo();
      setPhase('idle');
      setRect(null);
      return;
    }
    const target = TOUR_STEPS[index];
    if (target.tab !== activeTab) {
      if (activeTab === 'rank-preferences') undoRankDemo();
      onChangeTab(target.tab);
    }
    setStepIndex(index);
  };

  const startTour = () => {
    markTourSeen();
    setPhase('running');
    goToStep(0);
  };

  const dismissPrompt = () => {
    markTourSeen();
    setPhase('idle');
  };

  const skipTour = () => {
    if (step && step.tab === 'rank-preferences') undoRankDemo();
    setPhase('idle');
    setRect(null);
  };

  // Re-measures the target element on step/tab change and keeps tracking it across resize/scroll.
  useEffect(() => {
    if (!step) return undefined;

    const measure = () => {
      const el = document.querySelector(step.selector);
      setViewport({ width: window.innerWidth, height: window.innerHeight });
      setRect(el ? el.getBoundingClientRect() : null);
    };

    const el = document.querySelector(step.selector);
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    step.demo?.();

    measure();
    const scrollTimer = window.setTimeout(measure, 350);

    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => {
      window.clearTimeout(scrollTimer);
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [step, activeTab]);

  const tooltipStyle = useMemo(() => placeTooltip(rect, viewport), [rect, viewport]);

  return (
    <>
      <button type="button" className={styles.restartButton} onClick={startTour}>
        <span aria-hidden="true">🧭</span> Take a tour
      </button>

      {phase === 'prompt' && (
        <div className={styles.promptOverlay} role="dialog" aria-modal="true">
          <div className={styles.promptCard}>
            <h2 className={styles.promptTitle}>Want a quick tour of the site?</h2>
            <p className="subtitle">
              We'll walk through the tabs, filters, charts and the ranking sketchboard in about a minute.
            </p>
            <div className={styles.promptActions}>
              <button type="button" onClick={startTour}>Yes, show me</button>
              <button type="button" onClick={dismissPrompt}>No thanks</button>
            </div>
          </div>
        </div>
      )}

      {step && (
        <>
          <div className={styles.dimOverlay} />
          {rect && (
            <div
              className={styles.spotlight}
              style={{
                top: `${rect.top - 6}px`,
                left: `${rect.left - 6}px`,
                width: `${rect.width + 12}px`,
                height: `${rect.height + 12}px`,
              }}
            />
          )}
          <div className={styles.tooltip} style={tooltipStyle}>
            <p className={styles.tooltipCounter}>{stepIndex + 1} / {TOUR_STEPS.length}</p>
            <h3 className={styles.tooltipTitle}>{step.title}</h3>
            <p className={styles.tooltipText}>{step.text}</p>
            <div className={styles.tooltipControls}>
              <button type="button" onClick={skipTour} className={styles.skipButton}>Skip</button>
              <div className={styles.navButtons}>
                <button type="button" onClick={() => goToStep(stepIndex - 1)} disabled={stepIndex === 0}>
                  Back
                </button>
                <button type="button" onClick={() => goToStep(stepIndex + 1)}>
                  {stepIndex === TOUR_STEPS.length - 1 ? 'Finish' : 'Next'}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default Tour;
