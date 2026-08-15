import type { EndpointsSummary } from "../types/endpoints";

interface Props {
  summary: EndpointsSummary;
}

function Card({
  icon,
  label,
  value,
  color,
}: {
  icon: string;
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div
      className="rounded-[10px] border px-3.5 py-3 flex items-center gap-3"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div
        className="w-8 h-8 rounded-lg grid place-items-center shrink-0"
        style={{ background: color ? `${color}` : "var(--surf2)" }}
      >
        <i className={icon} style={{ fontSize: "15px", color: color ? "#fff" : "var(--tx-dim)" }} />
      </div>
      <div className="min-w-0">
        <div className="text-lg font-semibold leading-none tracking-tight" style={{ color: "var(--tx)" }}>
          {value}
        </div>
        <div className="text-[11px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>{label}</div>
      </div>
    </div>
  );
}

export default function EndpointsSummaryCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <Card icon="ph ph-desktop-tower" label="Total de endpoints" value={summary.total} />
      <Card icon="ph-fill ph-circle" label="Online" value={summary.online} color="var(--ok)" />
      <Card icon="ph-fill ph-circle" label="Offline" value={summary.offline} color="var(--off)" />
      <Card icon="ph-fill ph-plugs" label="Aislados" value={summary.isolated} color="var(--crit)" />
      <Card icon="ph-fill ph-warning" label="Críticos" value={summary.critical} color="var(--high)" />
    </div>
  );
}
