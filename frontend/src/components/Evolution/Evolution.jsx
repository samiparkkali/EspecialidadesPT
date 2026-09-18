import styles from './Evolution.module.css';

// Simple least-squares linear fit over the loaded years to project next
// year's total -- not a real forecast, just a visual trend cue.
function predictNext(points) {
  const n = points.length;
  if (n < 2) return null;
  const xs = points.map((p) => p.year);
  const ys = points.map((p) => p.seats);
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  const num = xs.reduce((sum, x, i) => sum + (x - meanX) * (ys[i] - meanY), 0);
  const den = xs.reduce((sum, x) => sum + (x - meanX) ** 2, 0);
  const slope = den === 0 ? 0 : num / den;
  const intercept = meanY - slope * meanX;
  const nextYear = Math.max(...xs) + 1;
  const seats = Math.max(0, Math.round(slope * nextYear + intercept));
  return { year: nextYear, seats };
}

const Evolution = ({ points }) => {
  if (!points.length) {
    return <p className="subtitle">No data for the selected filters.</p>;
  }

  const predicted = predictNext(points);
  const allPoints = predicted ? [...points, predicted] : points;

  const maxSeats = Math.max(...allPoints.map((p) => p.seats), 1);
  const width = 480;
  const height = 160;
  // Leave headroom above the tallest bar for its value label -- without it,
  // the max-value bar's label sits right at (or above) the chart's own top
  // edge and overlaps whatever is rendered above the chart.
  const topPad = 16;
  const barWidth = width / allPoints.length;

  const centers = allPoints.map((p, i) => ({
    x: i * barWidth + barWidth / 2,
    y: height - (p.seats / maxSeats) * (height - topPad),
  }));
  const trendPath = centers.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ');

  return (
    <div className="card" data-tour="evolution-chart">
      <h2 className={styles.title}>Seats by year</h2>
      <div className={styles.chartScroll} data-h-scroll>
      <svg viewBox={`0 0 ${width} ${height + 24}`} className={styles.chart}>
        {allPoints.map((p, i) => {
          const isPredicted = predicted && i === allPoints.length - 1;
          const barHeight = (p.seats / maxSeats) * (height - topPad);
          const x = i * barWidth + barWidth * 0.15;
          const barW = barWidth * 0.7;
          return (
            <g key={p.year}>
              <rect
                x={x}
                y={height - barHeight}
                width={barW}
                height={barHeight}
                rx={3}
                className={isPredicted ? styles.barPredicted : styles.bar}
              />
              <text
                x={x + barW / 2}
                y={height + 14}
                textAnchor="middle"
                className={isPredicted ? styles.labelPredicted : styles.label}
              >
                {p.year}
                {isPredicted ? '*' : ''}
              </text>
              <text
                x={x + barW / 2}
                y={height - barHeight - 4}
                textAnchor="middle"
                className={isPredicted ? styles.valuePredicted : styles.value}
              >
                {isPredicted ? `~${p.seats}` : p.seats}
              </text>
            </g>
          );
        })}
        {predicted && <path d={trendPath} className={styles.trendLine} />}
        {predicted && centers.map((c) => <circle key={c.x} cx={c.x} cy={c.y} r={2} className={styles.trendDot} />)}
      </svg>
      </div>
      {predicted && (
        <p className="subtitle">
          * {predicted.year} is a projection (simple trend line over the loaded years), not real data yet.
        </p>
      )}
    </div>
  );
};

export default Evolution;
