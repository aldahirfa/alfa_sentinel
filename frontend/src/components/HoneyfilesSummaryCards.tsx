import type { HoneyfilesSummary } from "../types/honeyfiles";

interface Props {
  summary: HoneyfilesSummary;
}

function Metric({ icon, label, value, tone = "brand", detail }: { icon: string; label: string; value: number; tone?: "brand" | "ok" | "warn" | "crit" | "off"; detail: string }) {
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
          <div className="text-[9px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[23px] font-bold leading-none mt-2 tracking-[-.04em] tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-mute)" }}>{detail}</div>
        </div>
      </div>
    </div>
  );
}

export default function HoneyfilesSummaryCards({ summary }: Props) {
  const total = Math.max(1, summary.total);
  const intactPct = Math.round((summary.active / total) * 100);
  const deploymentIssues = summary.pending_deployments + summary.failed_deployments;
  const requiresAttention = summary.triggered > 0 || deploymentIssues > 0;

  return (
    <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="absolute -right-16 -top-20 w-64 h-64 rounded-full pointer-events-none" style={{ background: "var(--brand-soft)", filter: "blur(38px)", opacity: .45 }} />

      <div className="relative z-[1] flex flex-col xl:flex-row gap-5 xl:items-center">
        <div className="xl:w-[31%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl grid place-items-center" style={{ background: requiresAttention ? "var(--warn-soft)" : "var(--brand-soft)", color: requiresAttention ? "var(--warn)" : "var(--brand)" }}>
              <i className="ph ph-file-lock" style={{ fontSize: "18px" }} />
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.17em] font-bold" style={{ color: "var(--brand)" }}>Cobertura de engaño</div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>{summary.total} honeyfiles registrados</div>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed mt-3 mb-0" style={{ color: "var(--tx-dim)" }}>
            Supervisa la disponibilidad e integridad de los archivos señuelo y cualquier interacción que pueda indicar actividad anómala.
          </p>

          <div className="grid grid-cols-2 gap-2 mt-4">
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Íntegros y activos</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: intactPct >= 90 ? "var(--ok)" : "var(--warn)" }}>{intactPct}%</div>
            </div>
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Con atención</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: deploymentIssues > 0 ? "var(--warn)" : "var(--tx)" }}>{deploymentIssues}</div>
            </div>
          </div>

          <div className="mt-3 h-[6px] rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
            <div className="h-full rounded-full" style={{ width: `${intactPct}%`, background: "linear-gradient(90deg, var(--brand), var(--info))" }} />
          </div>
        </div>

        <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Metric icon="ph-fill ph-shield-check" label="Activos" value={summary.active} tone="ok" detail="Señuelos operativos" />
          <Metric icon="ph-fill ph-warning-octagon" label="Activados" value={summary.triggered} tone={summary.triggered > 0 ? "crit" : "ok"} detail={summary.triggered > 0 ? "Requieren revisión" : "Sin activaciones"} />
          <Metric icon="ph ph-hourglass" label="Pendientes" value={summary.pending_deployments} tone={summary.pending_deployments > 0 ? "warn" : "brand"} detail="Esperando confirmación" />
          <Metric icon="ph ph-x-circle" label="Fallidos" value={summary.failed_deployments} tone={summary.failed_deployments > 0 ? "crit" : "off"} detail={summary.failed_deployments > 0 ? "Necesitan intervención" : "Sin fallos"} />
        </div>
      </div>
    </section>
  );
}
