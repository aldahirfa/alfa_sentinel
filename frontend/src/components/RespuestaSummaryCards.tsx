import type { RespuestaSummary } from "../types/respuesta";

interface Props {
  summary: RespuestaSummary;
}

function Card({ icon, label, value, color }: { icon: string; label: string; value: number; color?: string }) {
  return (
    <div
      className="rounded-xl border p-5 flex items-center gap-4 transition-premium hover:-translate-y-1"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)", boxShadow: "var(--shadow)" }}
    >
      <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0" style={{ background: color || "var(--surf2)" }}>
        <i className={icon} style={{ fontSize: "18px", color: color ? "#fff" : "var(--tx-dim)" }} />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-none tracking-tight mt-0.5" style={{ color: "var(--tx)" }}>{value}</div>
        <div className="text-[11.5px] mt-1 font-medium truncate" style={{ color: "var(--tx-mute)" }}>{label}</div>
      </div>
    </div>
  );
}

export default function RespuestaSummaryCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <Card icon="ph ph-plugs" label="Hosts aislados ahora" value={summary.isolated_now} />
      <Card icon="ph ph-clock-counter-clockwise" label="Aislamientos registrados (histórico)" value={summary.total_isolations} />
      <Card icon="ph-fill ph-siren" label="Incidentes críticos abiertos" value={summary.critical_incidents_open} color="var(--crit)" />
    </div>
  );
}
