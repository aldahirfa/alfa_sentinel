import type { RiskDistributionItem } from "../types/dashboard";

interface RiskDonutProps {
  data: RiskDistributionItem[];
  total: number;
}

const R = 54;
const CIRC = 2 * Math.PI * R;

export default function RiskDonut({ data, total }: RiskDonutProps) {
  const sum = data.reduce((s, d) => s + d.count, 0) || 1;
  const attention = data
    .filter((d) => d.level === "ALTO" || d.level === "CRÍTICO")
    .reduce((s, d) => s + d.count, 0);
  const attentionPct = total > 0 ? Math.round((attention / total) * 100) : 0;

  let cumulative = 0;
  const segments = data.map((d) => {
    const len = (d.count / sum) * CIRC;
    const offset = -((cumulative / sum) * CIRC);
    cumulative += d.count;
    return { ...d, len, offset, pct: Math.round((d.count / sum) * 100) };
  });

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden relative">
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: "linear-gradient(90deg, transparent, var(--info), transparent)", opacity: .45 }} />

      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
          <i className="ph ph-chart-donut" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--info)" }}>
            Exposición actual
          </div>
          <h2 className="text-[14.5px] font-semibold m-0 mt-1" style={{ color: "var(--tx)" }}>
            Distribución de riesgo
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Criticidad observada en endpoints monitoreados
          </div>
        </div>
      </div>

      <div className="flex items-center gap-5 mt-5 mb-4">
        <div className="relative w-[154px] h-[154px] shrink-0">
          <svg viewBox="0 0 140 140" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
            <circle cx="70" cy="70" r={R} fill="none" stroke="var(--surf3)" strokeWidth="14" />
            {segments
              .filter((s) => s.len > 0)
              .map((s) => (
                <circle
                  key={s.level}
                  cx="70"
                  cy="70"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="14"
                  strokeLinecap="round"
                  strokeDasharray={`${Math.max(0, s.len - 3).toFixed(1)} ${(CIRC - Math.max(0, s.len - 3)).toFixed(1)}`}
                  strokeDashoffset={s.offset.toFixed(1)}
                />
              ))}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
            <div className="text-[31px] font-bold tracking-[-.05em] leading-none" style={{ color: "var(--tx)" }}>
              {total}
            </div>
            <div className="text-[9.5px] mt-1.5 font-medium" style={{ color: "var(--tx-mute)" }}>
              endpoints
            </div>
            <div className="text-[9px] mt-1" style={{ color: attention > 0 ? "var(--high)" : "var(--ok)" }}>
              {attentionPct}% atención
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-2.5 min-w-0">
          {segments.map((item) => (
            <div key={item.level} className="min-w-0">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: item.color }} />
                <span className="truncate font-medium" style={{ color: "var(--tx-dim)" }}>{item.level}</span>
                <span className="ml-auto font-bold tabular-nums" style={{ color: "var(--tx)" }}>{item.count}</span>
                <span className="w-8 text-right text-[9.5px] tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.pct}%</span>
              </div>
              <div className="ml-4 mt-1.5 h-1 rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
                <div className="h-full rounded-full" style={{ width: `${item.pct}%`, background: item.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div
        className="mt-auto rounded-xl px-3.5 py-3 flex items-center gap-3"
        style={{
          background: attention > 0 ? "var(--high-soft)" : "var(--ok-soft)",
          border: `1px solid ${attention > 0 ? "var(--high-soft)" : "var(--ok-soft)"}`,
        }}
      >
        <div
          className="w-8 h-8 rounded-lg grid place-items-center"
          style={{ background: attention > 0 ? "var(--high-soft)" : "var(--ok-soft)", color: attention > 0 ? "var(--high)" : "var(--ok)" }}
        >
          <i className={attention > 0 ? "ph-fill ph-warning" : "ph-fill ph-shield-check"} style={{ fontSize: "16px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[11.5px] font-semibold" style={{ color: "var(--tx)" }}>
            {attention > 0 ? `${attention} endpoint${attention === 1 ? "" : "s"} requiere${attention === 1 ? "" : "n"} atención` : "Sin endpoints en riesgo alto o crítico"}
          </div>
          <div className="text-[9.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
            Clasificación consolidada con la telemetría disponible
          </div>
        </div>
      </div>
    </section>
  );
}
