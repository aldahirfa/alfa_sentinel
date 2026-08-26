import type { HoneyfilesSummary } from "../types/honeyfiles";

interface Props {
  summary: HoneyfilesSummary;
}

function Stat({
  icon,
  label,
  value,
  tone = "brand",
  detail,
}: {
  icon: string;
  label: string;
  value: number;
  tone?: "brand" | "ok" | "warn" | "crit" | "off";
  detail: string;
}) {
  const color = tone === "off" ? "var(--off)" : `var(--${tone})`;
  const soft = tone === "off" ? "var(--surf3)" : tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;

  return (
    <div className="rounded-2xl border px-4 py-4 relative overflow-hidden" style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 70%)`, opacity: .65 }} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[9px] font-bold tracking-[.13em] uppercase" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[27px] font-bold tracking-[-.04em] leading-none mt-2.5 tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-dim)" }}>{detail}</div>
        </div>
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: soft, color }}>
          <i className={icon} style={{ fontSize: "16px" }} />
        </div>
      </div>
    </div>
  );
}

export default function HoneyfilesSummaryCards({ summary }: Props) {
  const total = Math.max(1, summary.total);
  const intactPct = Math.round((summary.active / total) * 100);
  const deploymentIssues = summary.pending_deployments + summary.failed_deployments;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <section
        className="soc-panel-strong rounded-[22px] xl:col-span-5 p-5 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, var(--surf2), var(--surf) 58%, var(--bg-elevated))" }}
      >
        <div className="absolute -right-16 -top-20 w-52 h-52 rounded-full pointer-events-none" style={{ background: "radial-gradient(circle, var(--brand-glow), transparent 70%)" }} />
        <div className="relative z-[1]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Cobertura de engaño</div>
              <div className="text-[16px] font-semibold mt-1.5" style={{ color: "var(--tx)" }}>Estado de archivos señuelo</div>
              <p className="m-0 mt-2 text-[10.5px] leading-relaxed max-w-[420px]" style={{ color: "var(--tx-mute)" }}>
                Supervisa la disponibilidad de los honeyfiles desplegados y detecta cualquier interacción que pueda indicar actividad anómala.
              </p>
            </div>
            <div className="w-11 h-11 rounded-2xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <i className="ph ph-file-lock" style={{ fontSize: "21px" }} />
            </div>
          </div>

          <div className="flex items-end justify-between gap-5 mt-5">
            <div>
              <div className="text-[36px] font-bold tracking-[-.055em] leading-none tabular-nums" style={{ color: "var(--tx)" }}>{summary.total}</div>
              <div className="text-[10px] mt-1.5" style={{ color: "var(--tx-mute)" }}>honeyfiles registrados</div>
            </div>
            <div className="text-right">
              <div className="text-[24px] font-bold tracking-[-.04em] leading-none" style={{ color: intactPct >= 90 ? "var(--ok)" : "var(--warn)" }}>{intactPct}%</div>
              <div className="text-[9.5px] mt-1.5" style={{ color: "var(--tx-mute)" }}>íntegros y activos</div>
            </div>
          </div>

          <div className="h-2 rounded-full overflow-hidden mt-4" style={{ background: "var(--surf3)" }}>
            <div className="h-full rounded-full" style={{ width: `${intactPct}%`, background: "linear-gradient(90deg, var(--brand), var(--info))" }} />
          </div>

          <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
            <div>
              <div className="text-[9px]" style={{ color: "var(--tx-mute)" }}>Activos</div>
              <div className="text-[13px] font-bold mt-1" style={{ color: "var(--ok)" }}>{summary.active}</div>
            </div>
            <div>
              <div className="text-[9px]" style={{ color: "var(--tx-mute)" }}>Activados</div>
              <div className="text-[13px] font-bold mt-1" style={{ color: summary.triggered > 0 ? "var(--crit)" : "var(--tx-dim)" }}>{summary.triggered}</div>
            </div>
            <div>
              <div className="text-[9px]" style={{ color: "var(--tx-mute)" }}>Despliegues con atención</div>
              <div className="text-[13px] font-bold mt-1" style={{ color: deploymentIssues > 0 ? "var(--warn)" : "var(--tx-dim)" }}>{deploymentIssues}</div>
            </div>
          </div>
        </div>
      </section>

      <div className="xl:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Stat icon="ph-fill ph-warning-octagon" label="Activados / comprometidos" value={summary.triggered} tone={summary.triggered > 0 ? "crit" : "ok"} detail={summary.triggered > 0 ? "Requieren revisión inmediata" : "Sin activaciones registradas"} />
        <Stat icon="ph ph-hourglass" label="Despliegues pendientes" value={summary.pending_deployments} tone={summary.pending_deployments > 0 ? "warn" : "brand"} detail="Esperando confirmación del agente" />
        <Stat icon="ph ph-x-circle" label="Despliegues fallidos" value={summary.failed_deployments} tone={summary.failed_deployments > 0 ? "crit" : "off"} detail={summary.failed_deployments > 0 ? "Necesitan intervención" : "Sin fallos registrados"} />
        <Stat icon="ph-fill ph-shield-check" label="Honeyfiles íntegros" value={summary.active} tone="ok" detail={`${intactPct}% de la cobertura registrada`} />
      </div>
    </div>
  );
}
