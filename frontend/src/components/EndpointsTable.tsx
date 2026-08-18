import type { EndpointListItem } from "../types/endpoints";
import { severityPillStyle } from "../lib/severity";
import {
  AGENT_HEALTH_LABEL,
  AGENT_HEALTH_VAR,
  CONN_STATUS_LABEL,
  CONN_STATUS_VAR,
  connStatusPillStyle,
} from "../lib/endpointStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  endpoints: EndpointListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
  selectedId: number | null;
  flashId: number | null;
}

function rowAccent(ep: EndpointListItem): string | null {
  if (ep.risk === "CRÍTICO" || ep.conn_status === "ISOLATED") return "var(--crit)";
  if (ep.risk === "ALTO") return "var(--high)";
  if (ep.risk === "MEDIO") return "var(--warn)";
  return null;
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="py-3 pr-3">
          <div
            className="h-3.5 rounded animate-pulse"
            style={{ background: "var(--surf3)", width: i === 0 ? "70%" : "50%" }}
          />
        </td>
      ))}
    </tr>
  );
}

export default function EndpointsTable({ endpoints, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  return (
    <section
      className="rounded-xl border p-5 overflow-x-auto shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-widest uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">IP</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Riesgo</th>
            <th className="pb-2 pr-3 font-semibold">Agente</th>
            <th className="pb-2 pr-3 font-semibold">Última conexión</th>
            <th className="pb-2 pr-3 font-semibold">Alertas</th>
            <th className="pb-2 pr-3 font-semibold">Última actividad</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
          ) : endpoints.length === 0 ? (
            <tr>
              <td colSpan={9} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-magnifying-glass text-xl block mb-2" />
                {hasFilters
                  ? "Ningún endpoint coincide con la búsqueda o los filtros aplicados."
                  : "Todavía no hay endpoints registrados."}
              </td>
            </tr>
          ) : (
            endpoints.map((ep) => {
              const accent = rowAccent(ep);
              const isSelected = ep.id === selectedId;
              const isFlashing = ep.id === flashId;
              const selStyle = rowSelectionStyle(isSelected, isFlashing);
              return (
                <tr
                  key={ep.id}
                  className="border-t transition-colors cursor-pointer group"
                  style={{ borderColor: "var(--line-soft)", ...selStyle }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = selStyle.background as string)}
                >
                  <td className="py-3 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <div className="flex items-center gap-2.5 pl-2">
                      <i 
                        className={ep.operating_system.toLowerCase().includes("win") ? "ph-fill ph-windows-logo" : ep.operating_system.toLowerCase().includes("linux") ? "ph-fill ph-linux-logo" : "ph-fill ph-desktop"} 
                        style={{ fontSize: "18px", color: "var(--tx-dim)" }} 
                      />
                      <div>
                        <div className="font-bold tracking-tight" style={{ color: "var(--tx)" }}>{ep.hostname}</div>
                        <div className="text-[11px] mt-0.5 font-medium" style={{ color: "var(--tx-mute)" }}>
                          {ep.operating_system} {ep.os_version}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 pr-3 tabular-nums font-medium" style={{ color: "var(--tx-dim)" }}>{ep.ip_address}</td>
                  <td className="py-3 pr-3">
                    <span
                      className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full flex items-center gap-1.5 w-fit"
                      style={{ ...connStatusPillStyle(ep.conn_status), border: `1px solid ${connStatusPillStyle(ep.conn_status).color}` }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[ep.conn_status] }} />
                      {CONN_STATUS_LABEL[ep.conn_status]}
                    </span>
                  </td>
                  <td className="py-3 pr-3">
                    <span
                      className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full"
                      style={severityPillStyle(ep.risk)}
                    >
                      {ep.risk.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 pr-3">
                    <span className="flex items-center gap-1.5 font-medium" style={{ color: "var(--tx-dim)" }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: AGENT_HEALTH_VAR[ep.agent_health] }} />
                      {AGENT_HEALTH_LABEL[ep.agent_health]}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{ep.last_seen_ago}</td>
                  <td className="py-3 pr-3">
                    <span
                      className="font-bold tabular-nums"
                      style={{ color: ep.alerts_count > 0 ? "var(--warn)" : "var(--tx-mute)" }}
                    >
                      {ep.alerts_count}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>
                    {ep.last_activity_ago ?? "Sin actividad registrada"}
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => onSelect(ep.id)}
                      className="flex items-center gap-1.5 text-[11.5px] font-bold border-0 bg-transparent cursor-pointer whitespace-nowrap transition-premium btn-hover"
                      style={{ color: "var(--brand)" }}
                    >
                      Detalles
                      <i className="ph-fill ph-arrow-right text-[13px]" />
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </section>
  );
}
