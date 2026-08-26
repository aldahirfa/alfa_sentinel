import type { IncidentesSummary } from "../types/incidentes";

interface Props {
  summary: IncidentesSummary;
}

function Metric({ icon, label, value, tone, detail }: { icon: string; label: string; value: React.ReactNode; tone: string; detail: string }) {
  return (
    <div className="rounded-2xl border px-4 py-3.5 relative overflow-hidden" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${tone}, transparent 72%)`, opacity: .65 }} />
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: `color-mix(in srgb, ${tone} 12%, var(--surf3))`, color: tone }}>
          <i className={icon} style={{ fontSize: "15px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[23px] font-bold leading-none mt-2 tracking-[-.04em] tabular-nums" style={{ color: tone }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-mute)" }}>{detail}</div>
        </div>
      </div>
    </div>
  );
}

export default function IncidentesSummaryCards({ summary }: Props) {
  const urgent = summary.critical_incidents > 0 || summary.isolated_hosts > 0;

  return (
    <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="relative z-[1] flex flex-col xl:flex-row gap-5 xl:items-center">
        <div className="xl:w-[31%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl grid place-items-center" style={{ background: urgent ? "var(--crit-soft)" : "var(--brand-soft)", color: urgent ? "var(--crit)" : "var(--brand)" }}>
              <i className="ph-fill ph-siren" style={{ fontSize: "18px" }} />
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.17em] font-bold" style={{ color: "var(--brand)" }}>Gestión de incidentes</div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>
                {summary.critical_incidents > 0 ? `${summary.critical_incidents} caso${summary.critical_incidents === 1 ? "" : "s"} crítico${summary.critical_incidents === 1 ? "" : "s"}` : "Operación bajo control"}
              </div>
            </div>
          </div>
          <p className="text-[11px] leading-relaxed mt-3 mb-0" style={{ color: "var(--tx-dim)" }}>
            Consolida detecciones relacionadas en casos de investigación, asignación y respuesta para el equipo Blue Team.
          </p>
          <div className="mt-4 rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
            <div className="flex items-center justify-between text-[9.5px]">
              <span style={{ color: "var(--tx-mute)" }}>Tiempo medio de resolución</span>
              <span className="font-bold tabular-nums" style={{ color: "var(--tx)" }}>{summary.mttr_minutes !== null ? `${summary.mttr_minutes} min` : "Sin datos"}</span>
            </div>
          </div>
        </div>

        <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Metric icon="ph-fill ph-warning-octagon" label="Críticos" value={summary.critical_incidents} tone="var(--crit)" detail="Casos de prioridad inmediata" />
          <Metric icon="ph ph-warning" label="Alertas activas" value={summary.active_alerts} tone="var(--brand)" detail="Detecciones aún abiertas" />
          <Metric icon="ph ph-plugs" label="Hosts aislados" value={summary.isolated_hosts} tone={summary.isolated_hosts > 0 ? "var(--high)" : "var(--ok)"} detail="Endpoints bajo contención" />
        </div>
      </div>
    </section>
  );
}
