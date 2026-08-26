import type { RulesSummary } from "../types/rules";

interface Props {
  summary: RulesSummary;
}

function Metric({ label, value, icon, tone = "brand", detail }: { label: string; value: number; icon: string; tone?: "brand" | "ok" | "warn" | "off"; detail: string }) {
  const color = tone === "off" ? "var(--off)" : `var(--${tone})`;
  const soft = tone === "off" ? "var(--surf3)" : tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;

  return (
    <div className="rounded-2xl border px-4 py-3.5 relative overflow-hidden" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 72%)`, opacity: .65 }} />
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: soft, color }}>
          <i className={icon} style={{ fontSize: "15px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[9px] font-bold uppercase tracking-[.12em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[23px] font-bold tracking-[-.04em] leading-none mt-2 tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-mute)" }}>{detail}</div>
        </div>
      </div>
    </div>
  );
}

export default function RulesSummaryCards({ summary }: Props) {
  const total = Math.max(1, summary.total);
  const activePct = Math.round((summary.active / total) * 100);
  const requiresAttention = summary.inactive > 0 || activePct < 80;

  return (
    <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="absolute -right-16 -top-20 w-64 h-64 rounded-full pointer-events-none" style={{ background: "var(--brand-soft)", filter: "blur(38px)", opacity: .45 }} />

      <div className="relative z-[1] flex flex-col xl:flex-row gap-5 xl:items-center">
        <div className="xl:w-[31%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl grid place-items-center" style={{ background: requiresAttention ? "var(--warn-soft)" : "var(--brand-soft)", color: requiresAttention ? "var(--warn)" : "var(--brand)" }}>
              <i className="ph ph-circuitry" style={{ fontSize: "18px" }} />
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.17em] font-bold" style={{ color: "var(--brand)" }}>Motor heurístico</div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>{summary.total} reglas configuradas</div>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed mt-3 mb-0" style={{ color: "var(--tx-dim)" }}>
            Reglas que evalúan comportamiento de procesos, actividad de archivos y señales asociadas a ransomware.
          </p>

          <div className="grid grid-cols-2 gap-2 mt-4">
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Reglas activas</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: activePct >= 80 ? "var(--ok)" : "var(--warn)" }}>{activePct}%</div>
            </div>
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Inactivas</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: summary.inactive > 0 ? "var(--warn)" : "var(--tx)" }}>{summary.inactive}</div>
            </div>
          </div>

          <div className="mt-3 h-[6px] rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
            <div className="h-full rounded-full" style={{ width: `${activePct}%`, background: "linear-gradient(90deg, var(--brand), var(--info))" }} />
          </div>
        </div>

        <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Metric label="Reglas activas" value={summary.active} icon="ph-fill ph-check-circle" tone="ok" detail="Evaluándose actualmente" />
          <Metric label="Reglas inactivas" value={summary.inactive} icon="ph ph-pause-circle" tone={summary.inactive > 0 ? "warn" : "off"} detail="Fuera de evaluación" />
          <Metric label="Alertas · 30 días" value={summary.alerts_30d_total} icon="ph ph-warning" tone="brand" detail="Detecciones generadas" />
        </div>
      </div>
    </section>
  );
}
