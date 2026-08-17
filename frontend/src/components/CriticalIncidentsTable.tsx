import type { CriticalIncidentItem } from "../types/respuesta";
import { severityPillStyle } from "../lib/severity";

interface Props {
  items: CriticalIncidentItem[];
  loading: boolean;
}

export default function CriticalIncidentsTable({ items, loading }: Props) {
  return (
    <section
      className="rounded-xl border p-5 overflow-x-auto shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <h3 className="text-[14px] font-bold mb-4 tracking-tight" style={{ color: "var(--tx)" }}>
        Incidentes que requieren atención manual ahora
      </h3>
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-widest uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Código</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Severidad</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Responsable</th>
            <th className="pb-2 pr-3 font-semibold">Abierto</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 7 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8" style={{ color: "var(--tx-mute)" }}>
                <i className="ph-fill ph-shield-check text-xl block mb-2" style={{ color: "var(--ok)" }} />
                No hay incidentes de alta o crítica severidad abiertos ahora mismo.
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr
                key={item.id}
                className="border-t transition-colors cursor-pointer group"
                style={{ borderColor: "var(--line-soft)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "")}
              >
                <td className="py-3 pr-3 font-semibold" style={item.severity === "CRÍTICO" ? { boxShadow: "inset 3px 0 0 var(--crit)", paddingLeft: "8px" } : undefined}>
                  <span className="font-bold tracking-tight" style={{ color: "var(--tx)" }}>{item.code}</span>
                  <div className="text-[11px] mt-0.5 font-medium truncate max-w-[180px]" style={{ color: "var(--tx-mute)" }}>{item.title}</div>
                </td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                <td className="py-3 pr-3">
                  {item.severity && (
                    <span className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full" style={severityPillStyle(item.severity)}>
                      {item.severity.toUpperCase()}
                    </span>
                  )}
                </td>
                <td className="py-3 pr-3 font-bold" style={{ color: "var(--tx-dim)" }}>{item.status_label}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: item.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>
                  {item.assigned_to_name ?? "Sin asignar"}
                </td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.opened_at}</td>
                <td className="py-3">
                  <a
                    href={`/incidentes/${item.id}`}
                    className="flex items-center gap-1.5 text-[11.5px] font-bold no-underline whitespace-nowrap transition-premium btn-hover"
                    style={{ color: "var(--brand)" }}
                  >
                    Ver incidente
                    <i className="ph-fill ph-arrow-right text-[13px]" />
                  </a>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
