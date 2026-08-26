import type { AlertsSummary } from "../types/alerts";

interface Props {
  summary: AlertsSummary;
}

function Metric({
  icon,
  label,
  value,
  tone = "brand",
  detail,
}: {
  icon: string;
  label: string;
  value: number;
  tone?: "brand" | "crit" | "warn" | "ok";
  detail: string;
}) {
  const color = `var(--${tone})`;
  const soft = tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;

  return (
    <div
      className="rounded-2xl border px-4 py-3.5 relative overflow-hidden transition-premium hover:-translate-y-[1px]"
      style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}
    >
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, ${color}, transparent 72%)`, opacity: .65 }}
      />
      <div className="flex items-start gap-3">
        <div
          className="w-8 h-8 rounded-xl grid place-items-center shrink-0"
          style={{ background: soft, color }}
        >
          <i className={icon} style={{ fontSize: "15px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[9px] font-bold tracking-[.13em] uppercase" style={{ color: "var(--tx-mute)" }}>
            {label}
          </div>
          <div className="text-[24px] font-bold leading-none mt-2 tabular-nums tracking-[-.04em]" style={{ color }}>
            {value}
          </div>
          <div className="text-[9.5px] mt-2 leading-relaxed" style={{ color: "var(--tx-mute)" }}>
            {detail}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AlertsSummaryCards({ summary }: Props) {
  const activePct = summary.total > 0 ? Math.round((summary.active / summary.total) * 100) : 0;
  const criticalPct = summary.active > 0 ? Math.round((summary.critical / summary.active) * 100) : 0;
  const needsAttention = summary.active > 0 || summary.critical > 0;

  return (
    <section
      className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden"
      style={{
        background: needsAttention
          ? "linear-gradient(118deg, color-mix(in srgb, var(--crit) 7%, var(--surf)) 0%, var(--surf) 38%, color-mix(in srgb, var(--brand) 7%, var(--surf)) 100%)"
          : "linear-gradient(118deg, var(--surf) 0%, color-mix(in srgb, var(--brand) 7%, var(--surf)) 100%)",
      }}
    >
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="absolute -right-16 -top-20 w-64 h-64 rounded-full pointer-events-none" style={{ background: "var(--brand-soft)", filter: "blur(38px)", opacity: .55 }} />

      <div className="relative z-[1] flex flex-col xl:flex-row xl:items-center gap-5">
        <div className="xl:w-[31%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-2.5">
            <span
              className="w-9 h-9 rounded-xl grid place-items-center border"
              style={{
                color: needsAttention ? "var(--crit)" : "var(--brand)",
                background: needsAttention ? "var(--crit-soft)" : "var(--brand-soft)",
                borderColor: needsAttention ? "var(--crit-soft)" : "var(--brand-soft)",
              }}
            >
              <i className={needsAttention ? "ph-fill ph-warning-octagon" : "ph-fill ph-shield-check"} style={{ fontSize: "17px" }} />
            </span>
            <div>
              <div className="text-[9px] font-bold tracking-[.17em] uppercase" style={{ color: "var(--brand)" }}>
                Cola de detecciones
              </div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>
                {summary.critical > 0
                  ? `${summary.critical} alerta${summary.critical === 1 ? "" : "s"} crítica${summary.critical === 1 ? "" : "s"}`
                  : summary.active > 0
                    ? `${summary.active} alerta${summary.active === 1 ? "" : "s"} activa${summary.active === 1 ? "" : "s"}`
                    : "Sin alertas pendientes"}
              </div>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed mt-3 mb-0 max-w-[390px]" style={{ color: "var(--tx-dim)" }}>
            {summary.critical > 0
              ? "Existen detecciones de criticidad alta que deben revisarse antes de continuar con el flujo normal de análisis."
              : summary.active > 0
                ? "La cola operativa contiene detecciones pendientes de revisión, investigación o escalamiento."
                : "No hay detecciones abiertas que requieran intervención inmediata del equipo Blue Team."}
          </p>

          <div className="grid grid-cols-2 gap-2 mt-4">
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[9px] uppercase tracking-[.11em] font-bold" style={{ color: "var(--tx-mute)" }}>Activas / total</div>
              <div className="text-[16px] font-bold mt-1 tabular-nums" style={{ color: "var(--tx)" }}>{activePct}%</div>
            </div>
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[9px] uppercase tracking-[.11em] font-bold" style={{ color: "var(--tx-mute)" }}>Críticas / activas</div>
              <div className="text-[16px] font-bold mt-1 tabular-nums" style={{ color: summary.critical > 0 ? "var(--crit)" : "var(--tx)" }}>{criticalPct}%</div>
            </div>
          </div>
        </div>

        <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Metric icon="ph ph-pulse" label="Activas" value={summary.active} tone="brand" detail="Pendientes de atención" />
          <Metric icon="ph-fill ph-warning-octagon" label="Críticas" value={summary.critical} tone="crit" detail="Prioridad inmediata" />
          <Metric icon="ph ph-magnifying-glass" label="Investigación" value={summary.investigating} tone="warn" detail="Bajo análisis" />
          <Metric icon="ph-fill ph-check-circle" label="Resueltas" value={summary.resolved} tone="ok" detail="Cerradas correctamente" />
        </div>
      </div>

      <div className="relative z-[1] mt-4 pt-3 border-t flex items-center gap-3 text-[9.5px]" style={{ borderColor: "var(--line-soft)", color: "var(--tx-mute)" }}>
        <span className="flex items-center gap-1.5"><i className="ph ph-database" /> {summary.total} alertas registradas</span>
        <span className="w-1 h-1 rounded-full" style={{ background: "var(--line)" }} />
        <span>Vista operativa prioriza eventos que aún requieren acción.</span>
      </div>
    </section>
  );
}
