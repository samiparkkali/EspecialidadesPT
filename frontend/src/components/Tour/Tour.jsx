import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
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
// during render, so it stays stable across concurrent re-renders). `height`
// is the tooltip's own real measured height where available -- falling back
// to an estimate only for the very first render, before it's been measured --
// since a fixed estimate undershoots the real height on narrow screens
// (wrapped text, stacked buttons) and can push Next/Back off-screen.
const placeTooltip = (rect, viewport, height = TOOLTIP_HEIGHT_ESTIMATE) => {
  if (!rect || !viewport) {
    return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: `${TOOLTIP_WIDTH}px` };
  }
  const width = Math.min(TOOLTIP_WIDTH, viewport.width - MARGIN * 2);
  const maxHeight = viewport.height - MARGIN * 2;

  const spaceBelow = viewport.height - rect.bottom - MARGIN;
  const spaceAbove = rect.top - MARGIN;
  const spaceRight = viewport.width - rect.right - MARGIN;
  const spaceLeft = rect.left - MARGIN;

  let top;
  let left = rect.left + rect.width / 2 - width / 2;

  // Below and above are tried first (most natural reading position), but
  // only when they actually clear the spotlighted rect -- a short-on-room
  // target used to fall through to whichever side the clamp happened to
  // land on, which for a rect near the top of the viewport meant the
  // tooltip landed back on top of it instead of beside it. Falling back to
  // a side placement instead keeps the tooltip clear of its own target for
  // short/wide rects (a card, a bar); an extremely tall rect (taller than
  // the viewport) has no fully clear spot in any direction, so it's the one
  // case left to the vertical clamp below "below" as the least-bad choice.
  if (spaceBelow >= height) {
    top = rect.bottom + MARGIN;
  } else if (spaceAbove >= height) {
    top = rect.top - MARGIN - height;
  } else if (spaceRight >= width) {
    left = rect.right + MARGIN;
    top = Math.max(MARGIN, Math.min(rect.top, viewport.height - height - MARGIN));
  } else if (spaceLeft >= width) {
    left = rect.left - MARGIN - width;
    top = Math.max(MARGIN, Math.min(rect.top, viewport.height - height - MARGIN));
  } else {
    top = spaceBelow >= spaceAbove ? rect.bottom + MARGIN : rect.top - MARGIN - height;
  }
  top = Math.max(MARGIN, Math.min(top, viewport.height - height - MARGIN));
  left = Math.max(MARGIN, Math.min(left, viewport.width - width - MARGIN));

  return { top: `${top}px`, left: `${left}px`, width: `${width}px`, maxHeight: `${maxHeight}px`, overflowY: 'auto' };
};

const Tour = ({ activeTab, onChangeTab }) => {
  const [phase, setPhase] = useState(() => (hasSeenTour() ? 'idle' : 'prompt'));
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const [viewport, setViewport] = useState(null);
  const [tooltipHeight, setTooltipHeight] = useState(TOOLTIP_HEIGHT_ESTIMATE);
  const tooltipRef = useRef(null);

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

  // Placement above uses the tooltip's own real height once measured, since a
  // fixed estimate undershoots on narrow screens (wrapped text, stacked
  // buttons) and can otherwise push Next/Back past the bottom of the screen.
  // Intentionally runs after every render (no deps) to catch height changes
  // from content/viewport changes, not just rect/viewport swaps; the
  // threshold check inside prevents this from looping.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const measured = tooltipRef.current?.offsetHeight;
    if (measured && Math.abs(measured - tooltipHeight) > 1) setTooltipHeight(measured);
  });

  const tooltipStyle = useMemo(() => placeTooltip(rect, viewport, tooltipHeight), [rect, viewport, tooltipHeight]);

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
          <div ref={tooltipRef} className={styles.tooltip} style={tooltipStyle}>
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
