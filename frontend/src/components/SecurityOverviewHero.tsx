import type { DashboardOverview } from "../types/dashboard";

interface Props {
  data: DashboardOverview;
}

function Metric({
  label,
  value,
  icon,
  tone = "brand",
  detail,
}: {
  label: string;
  value: number;
  icon: string;
  tone?: "brand" | "warn" | "high" | "crit" | "ok";
  detail: string;
}) {
  const color = `var(--${tone})`;
  const soft = tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;

  return (
    <div
      className="rounded-2xl px-4 py-3.5 border relative overflow-hidden transition-premium hover:-translate-y-[1px]"
      style={{
        background: "color-mix(in srgb, var(--surf2) 82%, transparent)",
        borderColor: "var(--line-soft)",
      }}
    >
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 70%)`, opacity: .7 }} />
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-xl grid place-items-center shrink-0"
          style={{ background: soft, color }}
        >
          <i className={icon} style={{ fontSize: "16px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[9.5px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>
            {label}
          </div>
          <div className="text-[25px] leading-none font-bold tracking-[-.04em] mt-2 tabular-nums" style={{ color }}>
            {value}
          </div>
          <div className="text-[10px] mt-2 truncate" style={{ color: "var(--tx-dim)" }}>
            {detail}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SecurityOverviewHero({ data }: Props) {
  const { summary, endpoint_status: endpointStatus, system_status: systemStatus } = data;
  const criticalRisk = data.risk_distribution.find((item) => item.level === "CRÍTICO")?.count ?? 0;
  const highRisk = data.risk_distribution.find((item) => item.level === "ALTO")?.count ?? 0;
  const attentionCount = criticalRisk + highRisk;
  const totalEndpoints = Math.max(1, summary.endpoints_total);
  const onlinePct = Math.round((summary.endpoints_online / totalEndpoints) * 100);
  const hasImmediateRisk = summary.endpoints_isolated > 0 || criticalRisk > 0 || summary.incidents_active > 0;
  const hasOpenWork = hasImmediateRisk || summary.alerts_active > 0 || summary.honeyfiles_activated_today > 0;
  const allServicesOk = systemStatus.api_ok && systemStatus.db_ok && systemStatus.agents_comm_ok && systemStatus.detection_engine_ok;

  const stateColor = hasImmediateRisk ? "var(--crit)" : hasOpenWork ? "var(--warn)" : "var(--ok)";
  const stateSoft = hasImmediateRisk ? "var(--crit-soft)" : hasOpenWork ? "var(--warn-soft)" : "var(--ok-soft)";
  const stateIcon = hasImmediateRisk ? "ph-fill ph-warning-octagon" : hasOpenWork ? "ph-fill ph-warning" : "ph-fill ph-shield-check";
  const headline = hasImmediateRisk
    ? "Atención de seguridad requerida"
    : hasOpenWork
      ? "Actividad bajo supervisión"
      : "Entorno estable y monitoreado";
  const description = hasImmediateRisk
    ? "Existen eventos que requieren revisión o contención por parte del Blue Team."
    : hasOpenWork
      ? "El sistema mantiene detecciones activas que deben permanecer bajo seguimiento operacional."
      : "No se observan incidentes activos ni endpoints contenidos en este momento.";

  return (
    <section
      className="soc-panel-strong rounded-[22px] overflow-hidden relative min-h-[300px]"
      style={{ background: "linear-gradient(135deg, var(--surf2) 0%, var(--surf) 55%, var(--bg-elevated) 100%)" }}
    >
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div
        className="absolute -top-28 -right-24 w-[330px] h-[330px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, var(--brand-glow), transparent 68%)", opacity: .7 }}
      />

      <div className="relative z-[1] p-6">
        <div className="flex items-start gap-5 flex-wrap">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[9.5px] font-bold tracking-[.11em] uppercase border"
                style={{ background: stateSoft, color: stateColor, borderColor: stateSoft }}
              >
                <span className="relative flex w-2 h-2">
                  <span className="absolute inline-flex h-full w-full rounded-full opacity-30" style={{ background: stateColor }} />
                  <span className="relative inline-flex rounded-full w-2 h-2" style={{ background: stateColor }} />
                </span>
                Situación operacional
              </span>
              <span className="text-[10px]" style={{ color: "var(--tx-mute)" }}>
                actualización automática cada 20 s
              </span>
            </div>

            <div className="flex items-start gap-4 mt-5">
              <div
                className="w-14 h-14 rounded-[18px] grid place-items-center shrink-0 border"
                style={{ background: stateSoft, color: stateColor, borderColor: stateSoft }}
              >
                <i className={stateIcon} style={{ fontSize: "27px" }} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>
                  Blue Team · Estado actual
                </div>
                <h2 className="m-0 mt-2 text-[26px] leading-[1.08] font-bold tracking-[-.035em]" style={{ color: "var(--tx)" }}>
                  {headline}
                </h2>
                <p className="m-0 mt-2.5 max-w-[680px] text-[11.5px] leading-relaxed" style={{ color: "var(--tx-dim)" }}>
                  {description}
                </p>
              </div>
            </div>
          </div>

          <div
            className="w-full sm:w-auto sm:min-w-[225px] rounded-2xl border px-4 py-3.5"
            style={{ background: "color-mix(in srgb, var(--surf) 84%, transparent)", borderColor: "var(--line-soft)" }}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[9px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>
                  Superficie protegida
                </div>
                <div className="text-[28px] font-bold tracking-[-.045em] mt-1 tabular-nums" style={{ color: "var(--tx)" }}>
                  {onlinePct}%
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                <i className="ph ph-shield-chevron" style={{ fontSize: "20px" }} />
              </div>
            </div>

            <div className="h-2 rounded-full overflow-hidden mt-3" style={{ background: "var(--surf3)" }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${onlinePct}%`, background: "linear-gradient(90deg, var(--brand-strong), var(--info))" }}
              />
            </div>
            <div className="flex justify-between gap-3 mt-2 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>
              <span>{summary.endpoints_online} en línea</span>
              <span>{summary.endpoints_total} registrados</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mt-6">
          <Metric
            label="Alertas activas"
            value={summary.alerts_active}
            icon="ph ph-warning"
            tone={summary.alerts_active > 0 ? "warn" : "brand"}
            detail="Detecciones pendientes de revisión"
          />
          <Metric
            label="Incidentes activos"
            value={summary.incidents_active}
            icon="ph ph-siren"
            tone={summary.incidents_active > 0 ? "high" : "brand"}
            detail="Casos actualmente en investigación"
          />
          <Metric
            label="Endpoints aislados"
            value={summary.endpoints_isolated}
            icon="ph ph-plugs"
            tone={summary.endpoints_isolated > 0 ? "crit" : "brand"}
            detail="Equipos con contención de red"
          />
          <Metric
            label="Riesgo alto/crítico"
            value={attentionCount}
            icon="ph ph-crosshair"
            tone={criticalRisk > 0 ? "crit" : highRisk > 0 ? "high" : "ok"}
            detail={`${criticalRisk} críticos · ${highRisk} altos`}
          />
        </div>

        <div
          className="mt-4 pt-4 border-t grid grid-cols-2 lg:grid-cols-4 gap-x-5 gap-y-3 text-[10px]"
          style={{ borderColor: "var(--line-soft)", color: "var(--tx-mute)" }}
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: allServicesOk ? "var(--ok)" : "var(--crit)" }} />
            <span>Servicios</span>
            <b className="ml-auto" style={{ color: allServicesOk ? "var(--ok)" : "var(--crit)" }}>{allServicesOk ? "Operativos" : "Revisar"}</b>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: endpointStatus.agent_health_pct >= 90 ? "var(--ok)" : "var(--warn)" }} />
            <span>Salud de agentes</span>
            <b className="ml-auto" style={{ color: "var(--tx-dim)" }}>{endpointStatus.agent_health_pct.toFixed(1)}%</b>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: "var(--info)" }} />
            <span>Honeyfiles activos</span>
            <b className="ml-auto" style={{ color: "var(--tx-dim)" }}>{data.honeyfile_activity.active_total}</b>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: summary.honeyfiles_activated_today > 0 ? "var(--warn)" : "var(--brand)" }} />
            <span>Activados hoy</span>
            <b className="ml-auto" style={{ color: summary.honeyfiles_activated_today > 0 ? "var(--warn)" : "var(--tx-dim)" }}>{summary.honeyfiles_activated_today}</b>
          </div>
        </div>
      </div>
    </section>
  );
}
