import type { RulesSummary } from "../types/rules";

interface Props {
  summary: RulesSummary;
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

export default function RulesSummaryCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card icon="ph ph-list-checks" label="Reglas totales" value={summary.total} />
      <Card icon="ph-fill ph-check-circle" label="Reglas activas" value={summary.active} color="var(--ok)" />
      <Card icon="ph ph-pause-circle" label="Reglas inactivas" value={summary.inactive} color="var(--off)" />
      <Card icon="ph ph-warning" label="Alertas generadas (30 días)" value={summary.alerts_30d_total} color="var(--info)" />
    </div>
  );
}
