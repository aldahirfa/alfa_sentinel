interface Props {
  totalReports: number;
  lastGeneratedAt: string | null;
  lastGeneratedBy: string | null;
}

function Card({ icon, label, value, color }: { icon: string; label: string; value: React.ReactNode; color?: string }) {
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

export default function ReportsSummaryCards({ totalReports, lastGeneratedAt, lastGeneratedBy }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <Card icon="ph ph-chart-bar" label="Informes generados" value={totalReports} color="var(--info)" />
      <Card
        icon="ph ph-clock"
        label={lastGeneratedBy ? `Último informe -- ${lastGeneratedBy}` : "Último informe"}
        value={lastGeneratedAt ?? "—"}
      />
    </div>
  );
}
