import type { EndpointAtRisk } from "../types/dashboard";
import { SEVERITY_LABEL, SEVERITY_VAR, severityPillStyle } from "../lib/severity";

interface Props {
  endpoints: EndpointAtRisk[];
}

export default function EndpointsAtRisk({ endpoints }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="flex items-center">
        <h2 className="text-[14.5px] font-semibold m-0" style={{ color: "var(--tx)" }}>
          Endpoints que requieren atención
        </h2>
        <a
          href="/endpoints"
          className="ml-auto text-xs no-underline flex items-center gap-1"
          style={{ color: "var(--brand)" }}
        >
          Ver todos los endpoints
          <i className="ph ph-arrow-right text-[13px]" />
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
                className="flex items-center gap-3 px-3 py-2.5 rounded-[9px]"
                style={{
                  background: isCrit ? "var(--crit-soft)" : "var(--surf2)",
                  border: `1px solid ${isCrit ? "var(--crit-soft)" : "var(--line-soft)"}`,
                  boxShadow: `inset 3px 0 0 ${SEVERITY_VAR[ep.severity]}`,
                }}
              >
                <i
                  className="ph ph-desktop-tower text-[19px]"
                  style={{ color: SEVERITY_VAR[ep.severity] }}
                />
                <div className="min-w-0">
                  <div className="text-[13.5px] font-semibold" style={{ color: "var(--tx)" }}>
                    {ep.hostname}
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
                    {ep.os} · Último heartbeat: {ep.last_seen_ago}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-2.5 shrink-0">
                  <span className="text-[11px]" style={{ color: "var(--tx-dim)" }}>
                    Alertas activas: <b style={{ color: "var(--tx)" }}>{ep.alerts_count}</b>
                  </span>
                  <span
                    className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded"
                    style={severityPillStyle(ep.severity)}
                  >
                    {SEVERITY_LABEL[ep.severity].toUpperCase()}
                  </span>
                  <span
                    className="text-[10.5px] font-medium px-2 py-0.5 rounded flex items-center gap-1"
                    style={{ border: "1px solid var(--line)", color: "var(--tx-dim)" }}
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
