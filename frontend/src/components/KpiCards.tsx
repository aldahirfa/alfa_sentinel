import type { DashboardSummary } from "../types/dashboard";
import { isPlaceholderNumber, numOrPlaceholder } from "../lib/placeholder";

interface KpiCardsProps {
  summary: DashboardSummary;
}

function Card({
  icon,
  label,
  value,
  valueColor,
  sub,
  accent = "var(--brand)",
  highlighted,
}: {
  icon: string;
  label: string;
  value: React.ReactNode;
  valueColor?: string;
  sub?: React.ReactNode;
  accent?: string;
  highlighted?: boolean;
}) {
  return (
    <div
      className="group rounded-[14px] border px-4 py-4 relative overflow-hidden transition-premium hover:-translate-y-[2px]"
      style={{
        background: highlighted
          ? "linear-gradient(145deg, var(--crit-fill), var(--surf) 58%)"
          : "linear-gradient(145deg, var(--surf2), var(--surf) 56%)",
        borderColor: highlighted ? "color-mix(in srgb, var(--crit) 40%, var(--line))" : "var(--line-soft)",
        boxShadow: highlighted ? "0 0 0 1px var(--crit-soft), var(--shadow)" : "var(--shadow)",
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, ${accent}, transparent 68%)`, opacity: highlighted ? .9 : .55 }}
      />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] tracking-[.12em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            {label}
          </div>
          <div
            className="text-[30px] font-bold leading-none mt-3 tracking-[-.045em]"
            style={{ color: valueColor || "var(--tx)" }}
          >
            {value}
          </div>
        </div>
        <div
          className="w-9 h-9 rounded-[11px] grid place-items-center shrink-0 border transition-premium group-hover:scale-[1.03]"
          style={{
            background: `color-mix(in srgb, ${accent} 10%, var(--surf2))`,
            borderColor: `color-mix(in srgb, ${accent} 20%, var(--line-soft))`,
            color: accent,
          }}
        >
          <i className={icon} style={{ fontSize: "16px" }} />
        </div>
      </div>
      {sub && <div className="mt-3.5 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>{sub}</div>}
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />;
}

export default function KpiCards({ summary }: KpiCardsProps) {
  const trend = numOrPlaceholder(summary.alerts_trend_pct);
  const trendIsPlaceholder = isPlaceholderNumber(trend) && summary.alerts_trend_pct === null;
  const trendUp = trend > 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
      <Card
        icon="ph ph-desktop-tower"
        label="Endpoints protegidos"
        value={summary.endpoints_total}
        sub={
          <div className="flex gap-x-3 gap-y-1.5 flex-wrap text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>
            <span className="flex items-center gap-1.5"><Dot color="var(--ok)" />{summary.endpoints_online} en línea</span>
            <span className="flex items-center gap-1.5"><Dot color="var(--off)" />{summary.endpoints_offline} fuera de línea</span>
          </div>
        }
      />

      <Card
        icon="ph ph-warning"
        label="Alertas activas"
        value={summary.alerts_active}
        valueColor={summary.alerts_active > 0 ? "var(--warn)" : undefined}
        accent={summary.alerts_active > 0 ? "var(--warn)" : "var(--brand)"}
        sub={
          <div className="flex items-center gap-2 text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>
            <span
              className="flex items-center gap-1"
              style={{ color: trendIsPlaceholder ? "var(--tx-mute)" : trendUp ? "var(--high)" : "var(--ok)" }}
            >
              {!trendIsPlaceholder && <i className={trendUp ? "ph-fill ph-trend-up" : "ph-fill ph-trend-down"} style={{ fontSize: "12px" }} />}
              <b>{trendIsPlaceholder ? "Sin histórico" : `${trendUp ? "+" : ""}${trend}%`}</b>
            </span>
            <span>{trendIsPlaceholder ? "aún no hay 24 h previas" : "vs. período anterior"}</span>
          </div>
        }
      />

      <Card
        icon="ph ph-siren"
        label="Incidentes activos"
        value={summary.incidents_active}
        valueColor={summary.incidents_active > 0 ? "var(--high)" : undefined}
        accent={summary.incidents_active > 0 ? "var(--high)" : "var(--brand)"}
        sub={<div className="text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>Casos actualmente en investigación</div>}
      />

      <Card
        icon="ph-fill ph-plugs"
        label="Endpoints aislados"
        value={summary.endpoints_isolated}
        valueColor={summary.endpoints_isolated > 0 ? "var(--crit)" : undefined}
        highlighted={summary.endpoints_isolated > 0}
        accent={summary.endpoints_isolated > 0 ? "var(--crit)" : "var(--brand)"}
        sub={
          <div className="text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>
            {summary.endpoints_isolated === 0 ? "Sin equipos contenidos" : "Contención activa en la red"}
          </div>
        }
      />

      <Card
        icon="ph-fill ph-file-lock"
        label="Honeyfiles activados"
        value={summary.honeyfiles_activated_today}
        valueColor={summary.honeyfiles_activated_today > 0 ? "var(--warn)" : undefined}
        accent={summary.honeyfiles_activated_today > 0 ? "var(--warn)" : "var(--brand)"}
        sub={<div className="text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>Activaciones detectadas hoy</div>}
      />
    </div>
  );
}
