import { useEffect, useMemo, useRef, useState } from "react";

const PAD = { top: 14, right: 14, bottom: 26, left: 52 };

function ticks(min, max, count) {
  if (min === max) return [min];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + i * step);
}

// One series over time, in the theme's accent colour, with a crosshair and tooltip on hover.
// points: [{ date: "YYYY-MM-DD", value }]. invert: smaller is better and drawn higher (ranks).
export default function LineChart({ points, height = 240, fmtY, fmtTip, invert = false, yDomain, yTicks = 4, label }) {
  const wrap = useRef(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(260, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geo = useMemo(() => {
    if (!points.length) return null;
    const xs = points.map((p) => new Date(p.date).getTime());
    const ys = points.map((p) => p.value);
    const [x0, x1] = [xs[0], xs[xs.length - 1]];
    let [y0, y1] = yDomain || [Math.min(...ys), Math.max(...ys)];
    if (!yDomain) {
      const padY = (y1 - y0) * 0.08 || Math.abs(y1) * 0.05 || 1;
      y0 -= padY; y1 += padY;
    }
    const w = width - PAD.left - PAD.right;
    const h = height - PAD.top - PAD.bottom;
    const sx = (t) => PAD.left + (x1 === x0 ? w / 2 : ((t - x0) / (x1 - x0)) * w);
    const sy = (v) => PAD.top + (invert ? (v - y0) / (y1 - y0 || 1) : 1 - (v - y0) / (y1 - y0 || 1)) * h;
    const coords = points.map((p, i) => [sx(xs[i]), sy(p.value)]);
    const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
    const base = invert ? PAD.top : PAD.top + h;
    const area = `${line} L${coords[coords.length - 1][0].toFixed(1)} ${base} L${coords[0][0].toFixed(1)} ${base} Z`;
    const yt = ticks(y0, y1, yTicks).map((v) => ({ v, y: sy(v) }));
    const xIdx = [0, Math.floor((points.length - 1) / 2), points.length - 1];
    return { coords, line, area, yt, xIdx: [...new Set(xIdx)], w, h };
  }, [points, width, height, invert, yDomain, yTicks]);

  if (!geo) return null;

  const onMove = (clientX, el) => {
    const rect = el.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * width;
    let best = 0;
    for (let i = 1; i < geo.coords.length; i++) {
      if (Math.abs(geo.coords[i][0] - x) < Math.abs(geo.coords[best][0] - x)) best = i;
    }
    setHover(best);
  };

  const hp = hover != null ? geo.coords[hover] : null;
  const fewPoints = points.length <= 30;
  const tipLeft = hp ? Math.min(Math.max(hp[0], 70), width - 70) : 0;

  return (
    <div className="lineChart" ref={wrap} style={{ height }}>
      <svg width={width} height={height} role="img" aria-label={label}
        onMouseMove={(e) => onMove(e.clientX, e.currentTarget)} onMouseLeave={() => setHover(null)}
        onTouchStart={(e) => onMove(e.touches[0].clientX, e.currentTarget)}
        onTouchMove={(e) => onMove(e.touches[0].clientX, e.currentTarget)}>
        <defs>
          <linearGradient id="lcFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--accent)" stopOpacity={invert ? 0 : 0.22} />
            <stop offset="1" stopColor="var(--accent)" stopOpacity={invert ? 0.22 : 0} />
          </linearGradient>
        </defs>
        {geo.yt.map((t) => (
          <g key={t.v}>
            <line x1={PAD.left} x2={width - PAD.right} y1={t.y} y2={t.y} className="lineChart__grid" />
            <text x={PAD.left - 8} y={t.y + 4} className="lineChart__axis" textAnchor="end">{fmtY(t.v)}</text>
          </g>
        ))}
        {geo.xIdx.map((i, k) => (
          <text key={i} x={geo.coords[i][0]} y={height - 6} className="lineChart__axis"
            textAnchor={k === 0 ? "start" : k === geo.xIdx.length - 1 ? "end" : "middle"}>
            {new Date(points[i].date).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
          </text>
        ))}
        {points.length > 1 && <path d={geo.area} fill="url(#lcFill)" />}
        {points.length > 1 && <path d={geo.line} className="lineChart__line" />}
        {fewPoints && geo.coords.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={4} className="lineChart__dot" />)}
        {hp && (
          <g>
            <line x1={hp[0]} x2={hp[0]} y1={PAD.top} y2={height - PAD.bottom} className="lineChart__cross" />
            <circle cx={hp[0]} cy={hp[1]} r={5} className="lineChart__dot lineChart__dot--on" />
          </g>
        )}
      </svg>
      {hp && (
        <div className="lineChart__tip" style={{ left: tipLeft, top: Math.max(hp[1] - 52, 0) }}>
          <div className="lineChart__tipDate">
            {new Date(points[hover].date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </div>
          <div className="lineChart__tipValue">{(fmtTip || fmtY)(points[hover].value, points[hover])}</div>
        </div>
      )}
    </div>
  );
}
