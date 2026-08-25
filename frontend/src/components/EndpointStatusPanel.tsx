import type { EndpointStatus } from "../types/dashboard";

interface Props {
  status: EndpointStatus;
}

export default function EndpointStatusPanel({ status }: Props) {
  const total = status.online + status.offline + status.isolated || 1;
  const availabilityPct = Math.round((status.online / total) * 100);
  const segments = [
    { key: "online", label: "En línea", value: status.online, color: "var(--ok)" },
    { key: "offline", label: "Fuera de línea", value: status.offline, color: "var(--off)" },
    { key: "isolated", label: "Aislados", value: status.isolated, color: "var(--crit)" },
  ];

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-desktop-tower" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>
            Disponibilidad
          </div>
          <h2 className="text-[14px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Estado de endpoints
          </h2>
        </div>
        <div className="ml-auto text-right">
          <div className="text-[24px] leading-none font-bold tracking-[-.04em] tabular-nums" style={{ color: availabilityPct >= 90 ? "var(--ok)" : "var(--warn)" }}>
            {availabilityPct}%
          </div>
          <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>en línea</div>
        </div>
      </div>

      <div className="flex h-[8px] rounded-full overflow-hidden mt-5 gap-[2px]" style={{ background: "var(--surf3)" }}>
        {segments.map((s) => (
          s.value > 0 ? <div key={s.key} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} /> : null
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3">
        {segments.map((s) => (
          <div key={s.key} className="rounded-xl px-2.5 py-2.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
            <div className="flex items-center gap-1.5 text-[9px] truncate" style={{ color: "var(--tx-mute)" }}>
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: s.color }} />
              {s.label}
            </div>
            <div className="text-[16px] font-bold mt-1.5 tabular-nums" style={{ color: s.key === "isolated" && s.value > 0 ? "var(--crit)" : "var(--tx)" }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-3.5 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div className="flex items-center gap-2 mb-2">
          <div className="text-[10px] font-medium" style={{ color: "var(--tx-dim)" }}>Salud de agentes</div>
          <span className="ml-auto text-[10px] font-bold tabular-nums" style={{ color: status.agent_health_pct >= 90 ? "var(--ok)" : "var(--warn)" }}>
            {status.agent_health_pct.toFixed(1)}%
          </span>
        </div>
        <div className="h-[6px] rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
          <div
            className="h-full rounded-full transition-premium"
            style={{
              width: `${Math.max(0, Math.min(100, status.agent_health_pct))}%`,
              background: status.agent_health_pct >= 90 ? "linear-gradient(90deg, var(--brand), var(--ok))" : "var(--warn)",
            }}
          />
        </div>
      </div>
    </section>
  );
}
