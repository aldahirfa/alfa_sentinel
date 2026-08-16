import type { EndpointAtRisk } from "../types/dashboard";
import { SEVERITY_LABEL, SEVERITY_VAR, severityPillStyle } from "../lib/severity";

interface Props {
  endpoints: EndpointAtRisk[];
}

export default function EndpointsAtRisk({ endpoints }: Props) {
  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <div className="flex items-center">
        <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>
          Endpoints que requieren atención
        </h2>
        <a
          href="/endpoints"
          className="ml-auto text-xs font-bold no-underline flex items-center gap-1 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver todos los endpoints
          <i className="ph-fill ph-arrow-right text-[13px]" />
        </a>
      </div>

      {endpoints.length === 0 ? (
        <p className="text-[12.5px] py-6 text-center" style={{ color: "var(--tx-mute)" }}>
          Ningún endpoint tiene alertas abiertas en este momento.
        </p>
      ) : (
        <div className="flex flex-col gap-2 mt-3.5">
          {endpoints.map((ep) => {
            const isCrit = ep.severity === "CRITICAL";
            return (
              <div
                key={ep.hostname}
                className="flex items-center gap-3 px-3.5 py-3 rounded-xl transition-premium hover:-translate-y-1 hover:shadow-md cursor-pointer"
                style={{
                  background: isCrit ? "var(--crit-fill)" : "var(--surf2)",
                  border: `1px solid ${isCrit ? "var(--crit-soft)" : "var(--line-soft)"}`,
                  boxShadow: `inset 3px 0 0 ${SEVERITY_VAR[ep.severity]}`,
                }}
              >
                <i
                  className={ep.os.toLowerCase().includes("win") ? "ph-fill ph-windows-logo text-[24px]" : ep.os.toLowerCase().includes("linux") ? "ph-fill ph-linux-logo text-[24px]" : "ph-fill ph-desktop text-[24px]"}
                  style={{ color: SEVERITY_VAR[ep.severity] }}
                />
                <div className="min-w-0">
                  <div className="text-[14px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>
                    {ep.hostname}
                  </div>
                  <div className="text-[11.5px] mt-0.5 font-medium" style={{ color: "var(--tx-mute)" }}>
                    {ep.os} · Último heartbeat: {ep.last_seen_ago}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-2.5 shrink-0">
                  <span className="text-[11.5px] font-medium" style={{ color: "var(--tx-dim)" }}>
                    Alertas activas: <b style={{ color: "var(--tx)" }}>{ep.alerts_count}</b>
                  </span>
                  <span
                    className="text-[10px] font-bold tracking-wide px-2.5 py-0.5 rounded-full"
                    style={severityPillStyle(ep.severity)}
                  >
                    {SEVERITY_LABEL[ep.severity].toUpperCase()}
                  </span>
                  <span
                    className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full flex items-center gap-1.5"
                    style={{ border: "1px solid var(--line-soft)", color: "var(--tx-dim)", background: "var(--surf)" }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: ep.status === "ONLINE" ? "var(--ok)" : "var(--off)" }}
                    />
                    {ep.status === "ONLINE" ? "Online" : "Offline"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
