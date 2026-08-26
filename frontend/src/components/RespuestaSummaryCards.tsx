import type { RespuestaSummary } from "../types/respuesta";

interface Props {
  summary: RespuestaSummary;
}

function Metric({ label, value, icon, tone = "brand", detail }: { label: string; value: number; icon: string; tone?: "brand" | "crit" | "warn"; detail: string }) {
  const color = `var(--${tone})`;
  const soft = tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-soft)`;
  return (
    <div className="rounded-2xl border px-4 py-4 relative overflow-hidden" style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${color}, transparent 70%)`, opacity: .7 }} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[9px] font-bold uppercase tracking-[.13em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[29px] font-bold tracking-[-.045em] leading-none mt-2.5 tabular-nums" style={{ color }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-dim)" }}>{detail}</div>
        </div>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: soft, color }}>
          <i className={icon} style={{ fontSize: "16px" }} />
        </div>
      </div>
    </div>
  );
}

export default function RespuestaSummaryCards({ summary }: Props) {
  const requiresAttention = summary.isolated_now > 0 || summary.critical_incidents_open > 0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <section className="soc-panel-strong rounded-[22px] xl:col-span-5 p-5 relative overflow-hidden" style={{ background: "linear-gradient(135deg, var(--surf2), var(--surf) 58%, var(--bg-elevated))" }}>
        <div className="absolute -right-16 -top-20 w-52 h-52 rounded-full pointer-events-none" style={{ background: `radial-gradient(circle, ${requiresAttention ? "var(--crit-soft)" : "var(--brand-glow)"}, transparent 70%)` }} />
        <div className="relative z-[1]">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl grid place-items-center shrink-0" style={{ background: requiresAttention ? "var(--crit-soft)" : "var(--brand-soft)", color: requiresAttention ? "var(--crit)" : "var(--brand)" }}>
              <i className="ph ph-shield-warning" style={{ fontSize: "23px" }} />
            </div>
            <div>
              <div className="text-[9.5px] font-bold uppercase tracking-[.16em]" style={{ color: requiresAttention ? "var(--crit)" : "var(--brand)" }}>Estado de contención</div>
              <div className="text-[18px] font-semibold mt-1.5" style={{ color: "var(--tx)" }}>{requiresAttention ? "Respuesta activa en curso" : "Sin contenciones activas"}</div>
              <p className="m-0 mt-2 text-[10.5px] leading-relaxed" style={{ color: "var(--tx-mute)" }}>
                Seguimiento de aislamientos ejecutados y casos críticos que pueden requerir una acción manual del analista.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-5 pt-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
            <div>
              <div className="text-[9px] uppercase tracking-[.1em] font-semibold" style={{ color: "var(--tx-mute)" }}>Aislados ahora</div>
              <div className="text-[28px] font-bold mt-1.5" style={{ color: summary.isolated_now > 0 ? "var(--crit)" : "var(--tx)" }}>{summary.isolated_now}</div>
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.1em] font-semibold" style={{ color: "var(--tx-mute)" }}>Críticos abiertos</div>
              <div className="text-[28px] font-bold mt-1.5" style={{ color: summary.critical_incidents_open > 0 ? "var(--crit)" : "var(--tx)" }}>{summary.critical_incidents_open}</div>
            </div>
          </div>
        </div>
      </section>

      <div className="xl:col-span-7 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Metric label="Hosts aislados" value={summary.isolated_now} icon="ph ph-plugs" tone={summary.isolated_now > 0 ? "crit" : "brand"} detail="Contención vigente" />
        <Metric label="Histórico" value={summary.total_isolations} icon="ph ph-clock-counter-clockwise" tone="brand" detail="Aislamientos registrados" />
        <Metric label="Incidentes críticos" value={summary.critical_incidents_open} icon="ph-fill ph-siren" tone={summary.critical_incidents_open > 0 ? "crit" : "brand"} detail="Abiertos actualmente" />
      </div>
    </div>
  );
}
