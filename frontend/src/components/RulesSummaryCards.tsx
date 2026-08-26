import type { RulesSummary } from "../types/rules";

interface Props {
  summary: RulesSummary;
}

function Metric({ label, value, icon, tone = "brand", detail }: { label: string; value: number; icon: string; tone?: "brand" | "ok" | "warn" | "off"; detail: string }) {
  const color = tone === "off" ? "var(--off)" : `var(--${tone})`;
  const soft = tone === "off" ? "var(--surf3)" : tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;
  return (
    <div className="rounded-2xl border px-4 py-4 relative overflow-hidden" style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 70%)`, opacity: .65 }} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[9px] font-bold uppercase tracking-[.13em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[27px] font-bold tracking-[-.04em] leading-none mt-2.5 tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-dim)" }}>{detail}</div>
        </div>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: soft, color }}>
          <i className={icon} style={{ fontSize: "16px" }} />
        </div>
      </div>
    </div>
  );
}

export default function RulesSummaryCards({ summary }: Props) {
  const total = Math.max(1, summary.total);
  const activePct = Math.round((summary.active / total) * 100);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <section className="soc-panel-strong rounded-[22px] xl:col-span-6 p-5 relative overflow-hidden" style={{ background: "linear-gradient(135deg, var(--surf2), var(--surf) 58%, var(--bg-elevated))" }}>
        <div className="absolute -right-12 -top-16 w-48 h-48 rounded-full pointer-events-none" style={{ background: "radial-gradient(circle, var(--brand-glow), transparent 72%)" }} />
        <div className="relative z-[1]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[9.5px] font-bold uppercase tracking-[.16em]" style={{ color: "var(--brand)" }}>Motor heurístico</div>
              <div className="text-[16px] font-semibold mt-1.5" style={{ color: "var(--tx)" }}>Cobertura de reglas de detección</div>
              <p className="m-0 mt-2 text-[10.5px] leading-relaxed max-w-[460px]" style={{ color: "var(--tx-mute)" }}>
                Reglas activas que evalúan comportamiento de procesos, actividad de archivos y señales asociadas a ransomware.
              </p>
            </div>
            <div className="w-11 h-11 rounded-2xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <i className="ph ph-circuitry" style={{ fontSize: "21px" }} />
            </div>
          </div>

          <div className="flex items-end justify-between gap-4 mt-5">
            <div>
              <div className="text-[36px] font-bold tracking-[-.055em] leading-none" style={{ color: "var(--tx)" }}>{summary.total}</div>
              <div className="text-[10px] mt-1.5" style={{ color: "var(--tx-mute)" }}>reglas configuradas</div>
            </div>
            <div className="text-right">
              <div className="text-[24px] font-bold tracking-[-.04em] leading-none" style={{ color: activePct >= 80 ? "var(--ok)" : "var(--warn)" }}>{activePct}%</div>
              <div className="text-[9.5px] mt-1.5" style={{ color: "var(--tx-mute)" }}>activas</div>
            </div>
          </div>

          <div className="h-2 rounded-full overflow-hidden mt-4" style={{ background: "var(--surf3)" }}>
            <div className="h-full rounded-full" style={{ width: `${activePct}%`, background: "linear-gradient(90deg, var(--brand), var(--info))" }} />
          </div>
        </div>
      </section>

      <div className="xl:col-span-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Metric label="Reglas activas" value={summary.active} icon="ph-fill ph-check-circle" tone="ok" detail="Evaluándose actualmente" />
        <Metric label="Reglas inactivas" value={summary.inactive} icon="ph ph-pause-circle" tone={summary.inactive > 0 ? "warn" : "off"} detail="Fuera de evaluación" />
        <Metric label="Alertas · 30 días" value={summary.alerts_30d_total} icon="ph ph-warning" tone="brand" detail="Detecciones generadas" />
      </div>
    </div>
  );
}
