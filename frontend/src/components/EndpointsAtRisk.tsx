import type { EndpointAtRisk } from "../types/dashboard";
import { SEVERITY_VAR, severityPillStyle } from "../lib/severity";

interface Props {
  endpoints: EndpointAtRisk[];
}

function osIcon(os: string): string {
  const value = os.toLowerCase();
  if (value.includes("win")) return "ph-fill ph-windows-logo";
  if (value.includes("linux") || value.includes("ubuntu") || value.includes("debian")) return "ph-fill ph-linux-logo";
  return "ph-fill ph-desktop";
}

export default function EndpointsAtRisk({ endpoints }: Props) {
  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden relative">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-desktop-tower" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>
            Prioridad operativa
          </div>
          <h2 className="text-[14.5px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Endpoints que requieren atención
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Equipos con señales activas o mayor exposición actual
          </div>
        </div>
        <a
          href="/endpoints"
          className="ml-auto text-[10.5px] font-semibold no-underline flex items-center gap-1.5 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver endpoints
          <i className="ph ph-arrow-up-right" style={{ fontSize: "13px" }} />
        </a>
      </div>

      {endpoints.length === 0 ? (
        <div className="flex-1 min-h-[190px] flex flex-col items-center justify-center text-center px-5">
          <div className="w-11 h-11 rounded-2xl grid place-items-center" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
            <i className="ph-fill ph-shield-check" style={{ fontSize: "21px" }} />
          </div>
          <div className="text-[12px] font-semibold mt-3" style={{ color: "var(--tx)" }}>Sin endpoints prioritarios</div>
          <div className="text-[10.5px] mt-1 max-w-[280px]" style={{ color: "var(--tx-mute)" }}>
            Ningún equipo tiene alertas abiertas que requieran atención inmediata.
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 mt-4">
          {endpoints.map((ep) => {
            const isCrit = ep.severity === "CRÍTICO";
            const sevColor = SEVERITY_VAR[ep.severity];
            return (
              <a
                key={ep.hostname}
                href="/endpoints"
                className="group relative flex items-center gap-3.5 px-3.5 py-3 rounded-xl no-underline transition-premium overflow-hidden"
                style={{
                  background: isCrit ? "var(--crit-fill)" : "var(--surf2)",
                  border: `1px solid ${isCrit ? "var(--crit-soft)" : "var(--line-soft)"}`,
                }}
              >
                <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: sevColor }} />

                <div
                  className="w-9 h-9 rounded-xl grid place-items-center shrink-0"
                  style={{ background: "var(--brand-soft)", color: "var(--brand)", border: "1px solid var(--line-soft)" }}
                >
                  <i className={osIcon(ep.os)} style={{ fontSize: "17px" }} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[12.5px] font-semibold truncate" style={{ color: "var(--tx)" }}>
                      {ep.hostname}
                    </span>
                    <span className="text-[9px] font-bold tracking-wide px-2 py-0.5 rounded-md shrink-0" style={severityPillStyle(ep.severity)}>
                      {ep.severity.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-[10px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>
                    {ep.os} · heartbeat {ep.last_seen_ago}
                  </div>
                </div>

                <div className="hidden md:flex items-center gap-5 shrink-0">
                  <div className="text-right">
                    <div className="text-[9px] uppercase tracking-wider" style={{ color: "var(--tx-mute)" }}>Alertas</div>
                    <div className="text-[13px] font-bold tabular-nums mt-0.5" style={{ color: ep.alerts_count > 0 ? sevColor : "var(--tx)" }}>
                      {ep.alerts_count}
                    </div>
                  </div>
                  <div className="text-right min-w-[70px]">
                    <div className="text-[9px] uppercase tracking-wider" style={{ color: "var(--tx-mute)" }}>Agente</div>
                    <div className="flex items-center justify-end gap-1.5 text-[10px] font-semibold mt-1" style={{ color: ep.status === "ONLINE" ? "var(--ok)" : "var(--tx-mute)" }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: ep.status === "ONLINE" ? "var(--ok)" : "var(--off)" }} />
                      {ep.status === "ONLINE" ? "En línea" : "Fuera de línea"}
                    </div>
                  </div>
                </div>

                <i className="ph ph-caret-right shrink-0 transition-premium group-hover:translate-x-0.5" style={{ color: "var(--tx-mute)", fontSize: "13px" }} />
              </a>
            );
          })}
        </div>
      )}
    </section>
  );
}
