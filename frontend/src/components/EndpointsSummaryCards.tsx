import type { EndpointsSummary } from "../types/endpoints";

interface Props {
  summary: EndpointsSummary;
}

function Metric({ icon, label, value, tone, detail }: { icon: string; label: string; value: number; tone: string; detail: string }) {
  return (
    <div className="rounded-2xl border px-4 py-3.5 relative overflow-hidden" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, ${tone}, transparent 72%)`, opacity: .65 }} />
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: `color-mix(in srgb, ${tone} 12%, var(--surf3))`, color: tone }}>
          <i className={icon} style={{ fontSize: "15px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold uppercase tracking-[.12em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
          <div className="text-[23px] font-bold leading-none mt-2 tracking-[-.04em] tabular-nums" style={{ color: tone }}>{value}</div>
          <div className="text-[9.5px] mt-2" style={{ color: "var(--tx-mute)" }}>{detail}</div>
        </div>
      </div>
    </div>
  );
}

export default function EndpointsSummaryCards({ summary }: Props) {
  const available = Math.max(0, summary.total - summary.offline);
  const coveragePct = summary.total > 0 ? Math.round((available / summary.total) * 100) : 0;
  const protectedPct = summary.total > 0 ? Math.round((summary.online / summary.total) * 100) : 0;
  const needsAttention = summary.critical > 0 || summary.isolated > 0 || summary.offline > 0;

  return (
    <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
      <div className="blue-team-grid absolute inset-0 pointer-events-none" />
      <div className="relative z-[1] flex flex-col xl:flex-row gap-5 xl:items-center">
        <div className="xl:w-[32%] xl:pr-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl grid place-items-center" style={{ background: needsAttention ? "var(--brand-soft)" : "var(--ok-soft)", color: needsAttention ? "var(--brand)" : "var(--ok)" }}>
              <i className="ph-fill ph-desktop-tower" style={{ fontSize: "18px" }} />
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-[.17em] font-bold" style={{ color: "var(--brand)" }}>Superficie protegida</div>
              <div className="text-[15px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>{summary.total} endpoints registrados</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mt-4">
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Disponibilidad</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: coveragePct >= 90 ? "var(--ok)" : "var(--warn)" }}>{coveragePct}%</div>
            </div>
            <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
              <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>En línea</div>
              <div className="text-[18px] font-bold mt-1 tabular-nums" style={{ color: "var(--brand)" }}>{protectedPct}%</div>
            </div>
          </div>

          <div className="mt-3 h-[6px] rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
            <div className="h-full rounded-full" style={{ width: `${coveragePct}%`, background: coveragePct >= 90 ? "var(--ok)" : "var(--warn)" }} />
          </div>
        </div>

        <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Metric icon="ph-fill ph-circle" label="En línea" value={summary.online} tone="var(--ok)" detail="Agentes comunicando" />
          <Metric icon="ph ph-wifi-slash" label="Fuera de línea" value={summary.offline} tone={summary.offline > 0 ? "var(--warn)" : "var(--off)"} detail="Sin comunicación" />
          <Metric icon="ph-fill ph-plugs" label="Aislados" value={summary.isolated} tone={summary.isolated > 0 ? "var(--crit)" : "var(--brand)"} detail="Bajo contención" />
          <Metric icon="ph-fill ph-warning-octagon" label="Críticos" value={summary.critical} tone={summary.critical > 0 ? "var(--crit)" : "var(--brand)"} detail="Riesgo prioritario" />
        </div>
      </div>
    </section>
  );
}
