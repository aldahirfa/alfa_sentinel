import type { RecentAlert } from "../types/dashboard";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { textOrPlaceholder } from "../lib/placeholder";

interface Props {
  alerts: RecentAlert[];
}

export default function RecentAlertsTable({ alerts }: Props) {
  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <div className="flex items-center">
        <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>
          Alertas recientes
        </h2>
        <a
          href="/incidentes"
          className="ml-auto text-xs font-bold no-underline flex items-center gap-1 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver todas las alertas
          <i className="ph-fill ph-arrow-right text-[13px]" />
        </a>
      </div>

      <table className="w-full border-collapse mt-3 text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-2.5 font-semibold">Nivel</th>
            <th className="pb-2 pr-2.5 font-semibold">Endpoint</th>
            <th className="pb-2 pr-2.5 font-semibold">Detección</th>
            <th className="pb-2 pr-2.5 font-semibold">Proceso</th>
            <th className="pb-2 pr-2.5 font-semibold">Hora</th>
            <th className="pb-2 font-semibold">Estado</th>
          </tr>
        </thead>
        <tbody>
          {alerts.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center py-6" style={{ color: "var(--tx-mute)" }}>
                No hay alertas registradas.
              </td>
            </tr>
          ) : (
            alerts.map((a) => (
              <tr key={a.id} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                <td className="py-2.5 pr-2.5">
                  <span
                    className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded"
                    style={severityPillStyle(a.severity)}
                  >
                    {SEVERITY_LABEL[a.severity].toUpperCase()}
                  </span>
                </td>
                <td className="py-2.5 pr-2.5 font-medium" style={{ color: "var(--tx)" }}>{a.hostname}</td>
                <td className="py-2.5 pr-2.5" style={{ color: "var(--tx-dim)" }}>{a.title}</td>
                <td
                  className="py-2.5 pr-2.5 text-[11.5px]"
                  style={{ color: "var(--tx-dim)", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
                >
                  {textOrPlaceholder(a.process)}
                </td>
                <td className="py-2.5 pr-2.5" style={{ color: "var(--tx-dim)" }}>{a.time}</td>
                <td className="py-2.5" style={{ color: "var(--tx-dim)" }}>{a.status}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
