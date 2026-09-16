import styles from './Evolution.module.css';

const Evolution = ({ points }) => {
  if (!points.length) {
    return <p className="subtitle">Sem dados para os filtros selecionados.</p>;
  }

  const maxSeats = Math.max(...points.map((p) => p.seats), 1);
  const width = 480;
  const height = 160;
  const barWidth = width / points.length;

  return (
    <div className="card">
      <h2 className={styles.title}>Vagas por ano</h2>
      <svg viewBox={`0 0 ${width} ${height + 24}`} className={styles.chart} preserveAspectRatio="xMidYMid meet">
        {points.map((p, i) => {
          const barHeight = (p.seats / maxSeats) * height;
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
                className={styles.bar}
              />
              <text x={x + barW / 2} y={height + 14} textAnchor="middle" className={styles.label}>
                {p.year}
              </text>
              <text x={x + barW / 2} y={height - barHeight - 4} textAnchor="middle" className={styles.value}>
                {p.seats}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default Evolution;
