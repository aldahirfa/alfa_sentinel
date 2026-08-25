import type { RecentAlert } from "../types/dashboard";
import { severityPillStyle, SEVERITY_VAR } from "../lib/severity";
import { textOrPlaceholder } from "../lib/placeholder";

interface Props {
  alerts: RecentAlert[];
}

export default function RecentAlertsTable({ alerts }: Props) {
  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          <i className="ph ph-warning-octagon" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--crit)" }}>
            Detecciones recientes
          </div>
          <h2 className="text-[14.5px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Alertas recientes
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Últimos eventos generados por reglas heurísticas y mecanismos de engaño
          </div>
        </div>
        <a
          href="/alertas"
          className="ml-auto text-[10.5px] font-semibold no-underline flex items-center gap-1.5 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver alertas
          <i className="ph ph-arrow-up-right" style={{ fontSize: "13px" }} />
        </a>
      </div>

      <div className="overflow-x-auto mt-4 rounded-xl" style={{ border: "1px solid var(--line-soft)" }}>
        <table className="w-full border-collapse text-[11px] min-w-[760px]">
          <thead style={{ background: "var(--surf2)" }}>
            <tr className="text-left text-[9px] tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>
              <th className="px-3 py-2.5 font-semibold">Severidad</th>
              <th className="px-3 py-2.5 font-semibold">Detección</th>
              <th className="px-3 py-2.5 font-semibold">Endpoint</th>
              <th className="px-3 py-2.5 font-semibold">Proceso</th>
              <th className="px-3 py-2.5 font-semibold">Hora</th>
              <th className="px-3 py-2.5 font-semibold">Estado</th>
            </tr>
          </thead>
          <tbody>
            {alerts.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                  <i className="ph ph-shield-check block mb-2" style={{ fontSize: "20px", color: "var(--ok)" }} />
                  No hay alertas registradas.
                </td>
              </tr>
            ) : (
              alerts.map((a) => {
                const isCritical = a.severity === "CRÍTICO";
                return (
                  <tr
                    key={a.id}
                    className="border-t transition-premium"
                    style={{ borderColor: "var(--line-soft)", background: isCritical ? "var(--crit-fill)" : "transparent" }}
                  >
                    <td className="px-3 py-3">
                      <span className="text-[9px] font-bold tracking-wide px-2 py-1 rounded-md" style={severityPillStyle(a.severity)}>
                        {a.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-3 max-w-[240px]">
                      <div className="font-semibold truncate" style={{ color: isCritical ? SEVERITY_VAR[a.severity] : "var(--tx)" }}>
                        {a.title}
                      </div>
                      <div className="text-[9px] mt-1 mono-data" style={{ color: "var(--tx-mute)" }}>
                        ALR-{String(a.id).padStart(5, "0")}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                          <i className="ph ph-desktop-tower" style={{ fontSize: "12px" }} />
                        </span>
                        <span className="font-medium" style={{ color: "var(--tx-dim)" }}>{a.hostname}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 max-w-[160px]">
                      <span className="mono-data text-[10px] truncate block" style={{ color: "var(--tx-dim)" }}>
                        {textOrPlaceholder(a.process)}
                      </span>
                    </td>
                    <td className="px-3 py-3 tabular-nums whitespace-nowrap" style={{ color: "var(--tx-mute)" }}>{a.time}</td>
                    <td className="px-3 py-3">
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[9.5px] font-semibold"
                        style={{ background: "var(--surf2)", color: "var(--tx-dim)", border: "1px solid var(--line-soft)" }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: isCritical ? "var(--crit)" : "var(--brand)" }} />
                        {a.status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
