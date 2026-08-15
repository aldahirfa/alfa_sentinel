import type { HoneyfilesSummary } from "../types/honeyfiles";

interface Props {
  summary: HoneyfilesSummary;
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

export default function HoneyfilesSummaryCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <Card icon="ph ph-file-lock" label="Honeyfiles totales" value={summary.total} />
      <Card icon="ph-fill ph-shield-check" label="Activos (intactos)" value={summary.active} color="var(--ok)" />
      <Card icon="ph-fill ph-warning" label="Activados / comprometidos" value={summary.triggered} color="var(--crit)" />
      <Card icon="ph ph-hourglass" label="Despliegues pendientes" value={summary.pending_deployments} color="var(--info)" />
      <Card icon="ph ph-x-circle" label="Despliegues fallidos" value={summary.failed_deployments} color="var(--off)" />
    </div>
  );
}
