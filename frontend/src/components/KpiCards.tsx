import type { DashboardSummary } from "../types/dashboard";
import { isPlaceholderNumber, numOrPlaceholder } from "../lib/placeholder";

interface KpiCardsProps {
  summary: DashboardSummary;
}

function Card({
  icon,
  label,
  labelColor,
  value,
  valueColor,
  sub,
  accent,
  highlighted,
}: {
  icon: string;
  label: string;
  labelColor?: string;
  value: React.ReactNode;
  valueColor?: string;
  sub?: React.ReactNode;
  accent?: string;
  highlighted?: boolean;
}) {
  return (
    <div
      className="rounded-[10px] border p-4 relative overflow-hidden"
      style={{
        background: "var(--surf)",
        borderColor: highlighted ? "var(--crit)" : "var(--line)",
        boxShadow: highlighted ? "0 0 0 3px var(--crit-soft)" : "var(--shadow)",
      }}
    >
      {accent && (
        <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: accent }} />
      )}
      <div
        className="flex items-center gap-2 text-[10.5px] tracking-wider uppercase font-semibold"
        style={{ color: labelColor || "var(--tx-mute)" }}
      >
        <i className={icon} style={{ fontSize: "14px" }} />
        {label}
      </div>
      <div
        className="text-[34px] font-semibold leading-tight mt-2.5 tracking-tight"
        style={{ color: valueColor || "var(--tx)" }}
      >
        {value}
      </div>
      {sub}
    </div>
  );
}

function SubRow({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex gap-2.5 mt-3 pt-2.5 border-t text-[11px] flex-wrap"
      style={{ borderColor: "var(--line-soft)", color: "var(--tx-dim)" }}
    >
      {children}
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />;
}

export default function KpiCards({ summary }: KpiCardsProps) {
  const trend = numOrPlaceholder(summary.alerts_trend_pct);
  const trendIsPlaceholder = isPlaceholderNumber(trend) && summary.alerts_trend_pct === null;
  const trendUp = trend > 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
      <Card
        icon="ph ph-desktop-tower"
        label="Endpoints"
        value={summary.endpoints_total}
        sub={
          <SubRow>
            <span className="flex items-center gap-1.5">
              <Dot color="var(--ok)" />
              {summary.endpoints_online} Online
            </span>
            <span className="flex items-center gap-1.5">
              <Dot color="var(--crit)" />
              {summary.endpoints_isolated} Aislados
            </span>
            <span className="flex items-center gap-1.5">
              <Dot color="var(--off)" />
              {summary.endpoints_offline} Offline
            </span>
          </SubRow>
        }
      />

      <Card
        icon="ph ph-warning"
        label="Alertas activas"
        value={summary.alerts_active}
        valueColor="var(--warn)"
        sub={
          <SubRow>
            <span className="flex items-center gap-1" style={{ color: trendIsPlaceholder ? "var(--tx-mute)" : trendUp ? "var(--high)" : "var(--ok)" }}>
              <i className={trendUp ? "ph-fill ph-trend-up" : "ph-fill ph-trend-down"} style={{ fontSize: "13px" }} />
              <b>{trendUp ? "+" : ""}{trend}%</b>
            </span>
            {trendIsPlaceholder ? "dato de prueba -- sin 24h previas aún" : "respecto a las 24 h previas"}
          </SubRow>
        }
      />

      <Card
        icon="ph ph-siren"
        label="Incidentes activos"
        value={summary.incidents_active}
        valueColor="var(--high)"
        sub={<div className="text-[11.5px] mt-0.5" style={{ color: "var(--tx-dim)" }}>Incidentes en investigación</div>}
      />

      <Card
        icon="ph-fill ph-plugs"
        label="Endpoints aislados"
        labelColor={summary.endpoints_isolated > 0 ? "var(--crit)" : undefined}
        value={summary.endpoints_isolated}
        valueColor={summary.endpoints_isolated > 0 ? "var(--crit)" : undefined}
        highlighted={summary.endpoints_isolated > 0}
        accent={summary.endpoints_isolated > 0 ? "var(--crit)" : undefined}
        sub={
          <div className="text-[11px] mt-3 pt-2.5 border-t" style={{ borderColor: "var(--line-soft)", color: "var(--tx-dim)" }}>
            {summary.endpoints_isolated === 0
              ? "Ningún equipo contenido en este momento"
              : "Actualmente aislados"}
          </div>
        }
      />

      <Card
        icon="ph-fill ph-file-lock"
        label="Honeyfiles activados"
        labelColor={summary.honeyfiles_activated_today > 0 ? "var(--warn)" : undefined}
        value={summary.honeyfiles_activated_today}
        valueColor={summary.honeyfiles_activated_today > 0 ? "var(--warn)" : undefined}
        accent={summary.honeyfiles_activated_today > 0 ? "var(--warn)" : undefined}
        sub={<div className="text-[11.5px] mt-0.5" style={{ color: "var(--tx-dim)" }}>Activados hoy</div>}
      />
    </div>
  );
}
