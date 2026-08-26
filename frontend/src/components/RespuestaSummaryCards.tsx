import type { RespuestaSummary } from "../types/respuesta";

interface Props {
  summary: RespuestaSummary;
}

function Metric({ label, value, icon, tone = "brand", detail }: { label: string; value: number; icon: string; tone?: "brand" | "crit" | "warn" | "ok"; detail: string }) {
  const color = `var(--${tone})`;
  const soft = tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;

  return (
    <div className="rounded-2xl border px-4 py-3.5 relative overflow-hidden" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 72%)`, opacity: .65 }} />
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: soft, color }}>
          <i className={icon} style={{ fontSize: "15px" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[9px] font-bold uppercase tracking-[.12em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[23px] font-bold tracking-[-.04em] leading-none mt-2 tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-mute)" }}>{detail}</div>
        </div>
      </div>
    </div>
  );
}

export default function RespuestaSummaryCards({ summary }: Props) {
  const requiresAttention = summary.isolated_now > 0 || summary.critical_incidents_open > 0;

  return (
    <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="absolute -right-16 -top-20 w-64 h-64 rounded-full pointer-events-none" style={{ background: requiresAttention ? "var(--crit-soft)" : "var(--brand-soft)", filter: "blur(38px)", opacity: .42 }} />

      <div className="relative z-[1] flex flex-col xl:flex-row gap-5 xl:items-center">
        <div className="xl:w-[31%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl grid place-items-center" style={{ background: requiresAttention ? "var(--crit-soft)" : "var(--brand-soft)", color: requiresAttention ? "var(--crit)" : "var(--brand)" }}>
              <i className="ph ph-shield-warning" style={{ fontSize: "18px" }} />
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.17em] font-bold" style={{ color: requiresAttention ? "var(--crit)" : "var(--brand)" }}>Estado de contención</div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>{requiresAttention ? "Respuesta activa en curso" : "Sin contenciones activas"}</div>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed mt-3 mb-0" style={{ color: "var(--tx-dim)" }}>
            Seguimiento de aislamientos ejecutados y casos críticos que pueden requerir intervención del personal responsable.
          </p>

          <div className="grid grid-cols-2 gap-2 mt-4">
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Aislados ahora</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: summary.isolated_now > 0 ? "var(--crit)" : "var(--tx)" }}>{summary.isolated_now}</div>
            </div>
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Críticos abiertos</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: summary.critical_incidents_open > 0 ? "var(--crit)" : "var(--tx)" }}>{summary.critical_incidents_open}</div>
            </div>
          </div>
        </div>

        <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Metric label="Hosts aislados" value={summary.isolated_now} icon="ph ph-plugs" tone={summary.isolated_now > 0 ? "crit" : "brand"} detail="Contención vigente" />
          <Metric label="Histórico" value={summary.total_isolations} icon="ph ph-clock-counter-clockwise" tone="brand" detail="Aislamientos registrados" />
          <Metric label="Incidentes críticos" value={summary.critical_incidents_open} icon="ph-fill ph-siren" tone={summary.critical_incidents_open > 0 ? "crit" : "ok"} detail="Abiertos actualmente" />
        </div>
      </div>
    </section>
  );
}
