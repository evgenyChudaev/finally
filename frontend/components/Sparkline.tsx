'use client';

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}

/**
 * Hand-rolled SVG polyline sparkline. Lightweight Charts is overkill at this
 * scale (8x80 px per row), and an SVG keeps a static export tiny.
 */
export default function Sparkline({
  values,
  width = 80,
  height = 24,
  className,
}: SparklineProps) {
  if (!values || values.length < 2) {
    return (
      <svg width={width} height={height} className={className} aria-hidden>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#2a2f3a"
          strokeWidth={1}
          strokeDasharray="2 2"
        />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * stepX).toFixed(2)},${(height - ((v - min) / range) * height).toFixed(2)}`)
    .join(' ');

  const last = values[values.length - 1];
  const first = values[0];
  const isUp = last >= first;
  const stroke = isUp ? '#22c55e' : '#ef4444';

  return (
    <svg width={width} height={height} className={className} aria-hidden>
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
