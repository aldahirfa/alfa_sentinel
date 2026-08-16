import type { EndpointStatus } from "../types/dashboard";

interface Props {
  status: EndpointStatus;
}

export default function EndpointStatusPanel({ status }: Props) {
  const total = status.online + status.offline + status.isolated || 1;
  const segments = [
    { key: "online", value: status.online, color: "var(--ok)" },
    { key: "offline", value: status.offline, color: "var(--off)" },
    { key: "isolated", value: status.isolated, color: "var(--crit)" },
  ];

  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>
        Estado de endpoints
      </h2>

      <div className="flex h-[9px] rounded-[5px] overflow-hidden mt-auto gap-0.5 mb-1.5">
        {segments.map((s) => (
          <div key={s.key} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} />
        ))}
      </div>

      <div className="flex flex-col gap-2 mt-3">
        <div className="flex items-center gap-2 text-[12.5px]">
          <span className="w-2 h-2 rounded-full" style={{ background: "var(--ok)" }} />
          <span style={{ color: "var(--tx-dim)" }}>Online</span>
          <span className="ml-auto font-semibold" style={{ color: "var(--tx)" }}>{status.online}</span>
        </div>
        <div className="flex items-center gap-2 text-[12.5px]">
          <span className="w-2 h-2 rounded-full" style={{ background: "var(--off)" }} />
          <span style={{ color: "var(--tx-dim)" }}>Offline</span>
          <span className="ml-auto font-semibold" style={{ color: "var(--tx)" }}>{status.offline}</span>
        </div>
        <div className="flex items-center gap-2 text-[12.5px]">
          <span className="w-2 h-2 rounded-full" style={{ background: "var(--crit)" }} />
          <span style={{ color: "var(--tx-dim)" }}>Aislados</span>
          <span className="ml-auto font-semibold" style={{ color: "var(--crit)" }}>{status.isolated}</span>
        </div>
      </div>

      <div className="flex items-center gap-2.5 mt-3.5 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <span className="text-xs" style={{ color: "var(--tx-dim)" }}>Agent Health</span>
        <div className="flex-1 h-[5px] rounded-full overflow-hidden" style={{ background: "var(--surf3)" }}>
          <div className="h-full" style={{ width: `${status.agent_health_pct}%`, background: "var(--ok)" }} />
        </div>
        <span className="text-[12.5px] font-semibold" style={{ color: "var(--ok)" }}>
          {status.agent_health_pct.toFixed(1)}%
        </span>
      </div>
    </section>
  );
}
