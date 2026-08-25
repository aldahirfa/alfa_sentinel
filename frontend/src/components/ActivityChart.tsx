import { useEffect, useMemo, useState } from "react";
import { fetchActivitySeries } from "../api/client";
import type { ActivityRange, ActivitySeriesPoint } from "../types/dashboard";

const RANGE_OPTIONS: { value: ActivityRange; label: string; title: string }[] = [
  { value: "24h", label: "24 h", title: "Últimas 24 horas" },
  { value: "7d", label: "7 d", title: "Últimos 7 días" },
  { value: "30d", label: "30 d", title: "Últimos 30 días" },
];

const SERIES = [
  { key: "alerts" as const, label: "Alertas", color: "var(--brand)", width: 2.6 },
  { key: "activity" as const, label: "Actividad sospechosa", color: "var(--warn)", width: 2.1 },
  { key: "incidents" as const, label: "Incidentes", color: "var(--crit)", width: 2.1 },
  { key: "honeyfiles" as const, label: "Honeyfiles", color: "var(--info)", width: 1.9 },
];

const W = 900;
const H = 250;
const PT = 20;
const PB = 30;
const PL = 8;
const PR = 8;

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
    const maxValue = Math.max(1, ...seriesValues.flat());
    const max = maxValue * 1.2;
    const X = (i: number) => PL + (i * (W - PL - PR)) / Math.max(1, n - 1);
    const Y = (v: number) => H - PB - (v / max) * (H - PT - PB);

    const line = (arr: number[]) => smooth(arr.map((v, i) => [X(i), Y(v)]));
    const area = (arr: number[]) =>
      line(arr) + ` L${X(n - 1).toFixed(1)},${H - PB} L${X(0).toFixed(1)},${H - PB} Z`;

    const axisEvery = Math.max(1, Math.round(n / 6));
    const axis = points
      .map((p, i) => ({ label: p.bucket, i }))
      .filter(({ i }) => i % axisEvery === 0 || i === n - 1);

    return { X, Y, seriesValues, line, area, axis, n, maxValue };
  }, [points]);

  const tip = useMemo(() => {
    if (hover === null || !chart) return null;
    const pct = ((hover + 0.5) / chart.n) * 100;
    const p = points[hover];
    return {
      left: `${pct.toFixed(2)}%`,
      shift: pct > 62 ? "-100%" : pct < 12 ? "0%" : "-50%",
      bucket: p.bucket,
      values: SERIES.map((s) => ({ label: s.label, color: s.color, value: p[s.key] })),
    };
  }, [hover, chart, points]);

  const periodLabel = range === "24h" ? "Eventos por hora" : "Eventos por día";

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden relative">
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: "linear-gradient(90deg, transparent, var(--brand), transparent)", opacity: .55 }} />

      <div className="flex items-start gap-3 flex-wrap">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-wave-sine" style={{ fontSize: "18px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>
            Telemetría de amenazas
          </div>
          <h2 className="text-[14.5px] font-semibold m-0 mt-1" style={{ color: "var(--tx)" }}>
            Actividad de seguridad
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            {periodLabel} · señales procesadas por el Sistema ALFA-Sentinel
          </div>
        </div>

        <div className="ml-auto flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              title={opt.title}
              onClick={() => setRange(opt.value)}
              className="px-3 py-1.5 rounded-lg text-[10.5px] font-semibold border-0 cursor-pointer transition-premium"
              style={
                range === opt.value
                  ? { background: "var(--brand)", color: "#fff", boxShadow: "0 5px 16px var(--brand-glow)" }
                  : { background: "transparent", color: "var(--tx-mute)" }
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-x-4 gap-y-2 mt-4 flex-wrap text-[10.5px]" style={{ color: "var(--tx-dim)" }}>
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: s.color, boxShadow: `0 0 0 3px color-mix(in srgb, ${s.color} 14%, transparent)` }} />
            {s.label}
          </span>
        ))}
        {chart && (
          <span className="ml-auto text-[10px]" style={{ color: "var(--tx-mute)" }}>
            Pico del período: <b style={{ color: "var(--tx-dim)" }}>{chart.maxValue}</b>
          </span>
        )}
      </div>

      <div
        className="relative mt-3 flex-1 flex flex-col justify-end rounded-xl px-2 pt-2 overflow-hidden"
        style={{ background: "linear-gradient(180deg, var(--surf2), transparent)", border: "1px solid var(--line-soft)" }}
        onMouseLeave={() => setHover(null)}
      >
        <div className="blue-team-grid absolute inset-0 pointer-events-none" />
        {loading || !chart ? (
          <div className="h-[250px] flex flex-col items-center justify-center gap-2 text-xs" style={{ color: "var(--tx-mute)" }}>
            <i className={loading ? "ph ph-circle-notch animate-spin" : "ph ph-chart-line"} style={{ fontSize: "20px", color: "var(--brand)" }} />
            {loading ? "Cargando actividad..." : "Sin datos para este período."}
          </div>
        ) : (
          <>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block overflow-visible relative z-[1]">
              <defs>
                <linearGradient id="alertsArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.24" />
                  <stop offset="100%" stopColor="var(--brand)" stopOpacity="0.01" />
                </linearGradient>
              </defs>
              {[220, 170, 120, 70, 20].map((y, i) => (
                <line
                  key={y}
                  x1={8}
                  y1={y}
                  x2={892}
                  y2={y}
                  stroke={i === 0 ? "var(--line)" : "var(--line-soft)"}
                  strokeWidth={1}
                  strokeDasharray={i === 0 ? undefined : "4 6"}
                />
              ))}

              <path d={chart.area(chart.seriesValues[0])} fill="url(#alertsArea)" stroke="none" />

              {SERIES.map((s, i) => (
                <path
                  key={`l-${s.key}`}
                  d={chart.line(chart.seriesValues[i])}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.width}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}

              {hover !== null && SERIES.map((s, i) => (
                <circle
                  key={`p-${s.key}`}
                  cx={chart.X(hover)}
                  cy={chart.Y(chart.seriesValues[i][hover])}
                  r="4"
                  fill={s.color}
                  stroke="var(--surf)"
                  strokeWidth="2"
                />
              ))}
            </svg>

            <div className="absolute left-2 right-2 top-2 z-[2] flex" style={{ bottom: 30 }}>
              {points.map((_, i) => (
                <div key={i} className="flex-1 h-full" onMouseEnter={() => setHover(i)} />
              ))}
            </div>

            {tip && (
              <>
                <div
                  className="absolute top-2 w-px z-[2]"
                  style={{ bottom: 30, background: "var(--brand)", opacity: .35, left: tip.left }}
                />
                <div
                  className="absolute top-3 rounded-xl px-3 py-2.5 pointer-events-none z-10"
                  style={{
                    left: tip.left,
                    transform: `translateX(${tip.shift})`,
                    background: "var(--surf3)",
                    border: "1px solid var(--line)",
                    boxShadow: "var(--shadow-lg)",
                    minWidth: 190,
                  }}
                >
                  <div className="text-[10px] font-semibold mb-2" style={{ color: "var(--tx-mute)" }}>{tip.bucket}</div>
                  {tip.values.map((v) => (
                    <div key={v.label} className="flex items-center gap-2 text-[11px] py-0.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: v.color }} />
                      <span style={{ color: "var(--tx-dim)" }}>{v.label}</span>
                      <span className="ml-auto font-bold tabular-nums" style={{ color: "var(--tx)" }}>{v.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="flex justify-between text-[9.5px] px-1 pb-2 relative z-[1]" style={{ color: "var(--tx-mute)" }}>
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
