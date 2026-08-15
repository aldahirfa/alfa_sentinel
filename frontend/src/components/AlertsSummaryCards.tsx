import type { AlertsSummary } from "../types/alerts";

interface Props {
  summary: AlertsSummary;
}

function Card({ icon, label, value, color }: { icon: string; label: string; value: number; color?: string }) {
  return (
    <div
      className="rounded-[10px] border px-3.5 py-3 flex items-center gap-3"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="w-8 h-8 rounded-lg grid place-items-center shrink-0" style={{ background: color || "var(--surf2)" }}>
        <i className={icon} style={{ fontSize: "15px", color: color ? "#fff" : "var(--tx-dim)" }} />
      </div>
      <div className="min-w-0">
        <div className="text-lg font-semibold leading-none tracking-tight" style={{ color: "var(--tx)" }}>{value}</div>
        <div className="text-[11px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>{label}</div>
      </div>
    </div>
  );
}

export default function AlertsSummaryCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <Card icon="ph ph-warning" label="Todas" value={summary.total} />
      <Card icon="ph-fill ph-pulse" label="Activas" value={summary.active} color="var(--info)" />
      <Card icon="ph-fill ph-warning" label="Críticas" value={summary.critical} color="var(--crit)" />
      <Card icon="ph ph-magnifying-glass" label="En investigación" value={summary.investigating} color="var(--warn)" />
      <Card icon="ph-fill ph-check-circle" label="Resueltas" value={summary.resolved} color="var(--ok)" />
    </div>
  );
}
