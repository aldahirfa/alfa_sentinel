import { useEffect, useMemo, useState } from "react";
import { fetchActivitySeries } from "../api/client";
import type { ActivityRange, ActivitySeriesPoint } from "../types/dashboard";

// Curvas suaves + tooltip por hover, portado del mockup real
// (Panel de control AGETIC/...dc.html, método chart()/tip() de su
// clase Component) a un componente React -- misma lógica de
// interpolación Catmull-Rom, datos reales de
// /api/dashboard/activity-series en vez de la data de ejemplo fija
// del mockup.

const RANGE_OPTIONS: { value: ActivityRange; label: string }[] = [
  { value: "24h", label: "Últimas 24 horas" },
  { value: "7d", label: "Últimos 7 días" },
  { value: "30d", label: "Últimos 30 días" },
];

const SERIES = [
  { key: "alerts" as const, label: "Alertas", color: "var(--brand)", fill: "var(--brand-fill)", width: 2 },
  { key: "activity" as const, label: "Actividad sospechosa", color: "var(--warn)", fill: "var(--warn-fill)", width: 1.8 },
  { key: "incidents" as const, label: "Incidentes", color: "var(--crit)", fill: null, width: 1.8 },
  { key: "honeyfiles" as const, label: "Honeyfiles", color: "var(--info)", fill: null, width: 1.6 },
];

const W = 900, H = 240, PT = 18, PB = 28, PL = 8, PR = 8;

function smooth(pts: [number, number][]): string {
  if (pts.length === 0) return "";
  let out = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    out += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return out;
}

export default function ActivityChart() {
  const [range, setRange] = useState<ActivityRange>("24h");
  const [points, setPoints] = useState<ActivitySeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setHover(null);
    fetchActivitySeries(range)
      .then((res) => {
        if (!cancelled) setPoints(res.points);
      })
      .catch(() => {
        if (!cancelled) setPoints([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [range]);

  const chart = useMemo(() => {
    const n = points.length;
    if (n === 0) return null;

    const seriesValues = SERIES.map((s) => points.map((p) => p[s.key]));
    const max = Math.max(1, ...seriesValues.flat()) * 1.18;
    const X = (i: number) => PL + (i * (W - PL - PR)) / Math.max(1, n - 1);
    const Y = (v: number) => H - PB - (v / max) * (H - PT - PB);

    const line = (arr: number[]) => smooth(arr.map((v, i) => [X(i), Y(v)]));
    const area = (arr: number[]) =>
      line(arr) + ` L${X(n - 1).toFixed(1)},${H - PB} L${X(0).toFixed(1)},${H - PB} Z`;

    const axisEvery = Math.max(1, Math.round(n / 6));
    const axis = points
      .map((p, i) => ({ label: p.bucket, i }))
      .filter(({ i }) => i % axisEvery === 0 || i === n - 1);

    return { X, seriesValues, line, area, axis, n };
  }, [points]);

  const tip = useMemo(() => {
    if (hover === null || !chart) return null;
    const n = chart.n;
    const pct = ((hover + 0.5) / n) * 100;
    const p = points[hover];
    return {
      left: `${pct.toFixed(2)}%`,
      shift: pct > 62 ? "-100%" : pct < 12 ? "0%" : "-50%",
      bucket: p.bucket,
      values: SERIES.map((s) => ({ label: s.label, color: s.color, value: p[s.key] })),
    };
  }, [hover, chart, points]);

  return (
    <section
      className="rounded-[10px] border p-4 pb-3"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="flex items-center gap-3.5 flex-wrap">
        <div>
          <h2 className="text-[14.5px] font-semibold m-0" style={{ color: "var(--tx)" }}>
            Actividad de seguridad
          </h2>
          <div className="text-[11.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
            {range === "24h" ? "Últimas 24 horas · eventos por hora" : range === "7d" ? "Últimos 7 días · eventos por día" : "Últimos 30 días · eventos por día"}
          </div>
        </div>
        <div className="ml-auto flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRange(opt.value)}
              className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
              style={
                range === opt.value
                  ? { background: "var(--brand-soft)", color: "var(--brand)" }
                  : { background: "transparent", color: "var(--tx-mute)" }
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-4 mt-3 flex-wrap text-[11.5px]" style={{ color: "var(--tx-dim)" }}>
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>

      <div className="relative mt-1.5" onMouseLeave={() => setHover(null)}>
        {loading || !chart ? (
          <div className="h-[240px] flex items-center justify-center text-xs" style={{ color: "var(--tx-mute)" }}>
            {loading ? "Cargando actividad..." : "Sin datos para este período."}
          </div>
        ) : (
          <>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block overflow-visible">
              {[212, 165, 118, 71, 24].map((y, i) => (
                <line key={y} x1={8} y1={y} x2={892} y2={y} stroke={i === 0 ? "var(--line)" : "var(--line-soft)"} strokeWidth={1} />
              ))}
              {SERIES.map((s, i) =>
                s.fill ? (
                  <path key={`a-${s.key}`} d={chart.area(chart.seriesValues[i])} fill={s.fill} stroke="none" />
                ) : null
              )}
              {SERIES.map((s, i) => (
                <path
                  key={`l-${s.key}`}
                  d={chart.line(chart.seriesValues[i])}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.width}
                  strokeLinecap="round"
                />
              ))}
            </svg>
            <div className="absolute left-0 right-0 top-0 flex" style={{ bottom: 28 }}>
              {points.map((_, i) => (
                <div key={i} className="flex-1 h-full" onMouseEnter={() => setHover(i)} />
              ))}
            </div>
            {tip && (
              <>
                <div
                  className="absolute top-0 w-px opacity-50"
                  style={{ bottom: 28, background: "var(--tx-mute)", left: tip.left }}
                />
                <div
                  className="absolute top-1 rounded-lg px-2.5 py-2 pointer-events-none z-10"
                  style={{
                    left: tip.left,
                    transform: `translateX(${tip.shift})`,
                    background: "var(--surf3)",
                    border: "1px solid var(--line)",
                    boxShadow: "0 8px 24px rgba(0,0,0,.28)",
                    minWidth: 186,
                  }}
                >
                  <div className="text-[11px] mb-1.5" style={{ color: "var(--tx-mute)" }}>{tip.bucket}</div>
                  {tip.values.map((v) => (
                    <div key={v.label} className="flex items-center gap-1.5 text-[11.5px] py-px">
                      <span className="w-1.5 h-1.5 rounded-sm" style={{ background: v.color }} />
                      {v.label}
                      <span className="ml-auto font-semibold" style={{ color: "var(--tx)" }}>{v.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
            <div className="flex justify-between text-[10.5px] px-1 pb-1" style={{ color: "var(--tx-mute)" }}>
              {chart.axis.map(({ label, i }) => (
                <span key={i}>{label}</span>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
