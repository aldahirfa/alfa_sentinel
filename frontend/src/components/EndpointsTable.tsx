import type { EndpointListItem } from "../types/endpoints";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import {
  AGENT_HEALTH_LABEL,
  AGENT_HEALTH_VAR,
  CONN_STATUS_LABEL,
  CONN_STATUS_VAR,
  connStatusPillStyle,
} from "../lib/endpointStatus";

interface Props {
  endpoints: EndpointListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
}

function rowAccent(ep: EndpointListItem): string | null {
  if (ep.risk === "CRITICAL" || ep.conn_status === "ISOLATED") return "var(--crit)";
  if (ep.risk === "HIGH") return "var(--high)";
  if (ep.risk === "SUSPICIOUS") return "var(--warn)";
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

export default function EndpointsTable({ endpoints, loading, hasFilters, onSelect }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">IP</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Riesgo</th>
            <th className="pb-2 pr-3 font-semibold">Agente</th>
            <th className="pb-2 pr-3 font-semibold">Heartbeat</th>
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
              return (
                <tr
                  key={ep.id}
                  className="border-t transition-colors"
                  style={{ borderColor: "var(--line-soft)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                >
                  <td className="py-2.5 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <div className="font-semibold pl-2" style={{ color: "var(--tx)" }}>{ep.hostname}</div>
                    <div className="text-[11px] mt-0.5 pl-2" style={{ color: "var(--tx-mute)" }}>
                      {ep.operating_system} {ep.os_version}
                    </div>
                  </td>
                  <td className="py-2.5 pr-3 tabular-nums" style={{ color: "var(--tx-dim)" }}>{ep.ip_address}</td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="text-[10.5px] font-medium px-2 py-0.5 rounded flex items-center gap-1.5 w-fit"
                      style={connStatusPillStyle(ep.conn_status)}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[ep.conn_status] }} />
                      {CONN_STATUS_LABEL[ep.conn_status]}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded"
                      style={severityPillStyle(ep.risk)}
                    >
                      {SEVERITY_LABEL[ep.risk].toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className="flex items-center gap-1.5" style={{ color: "var(--tx-dim)" }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: AGENT_HEALTH_VAR[ep.agent_health] }} />
                      {AGENT_HEALTH_LABEL[ep.agent_health]}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{ep.last_seen_ago}</td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="font-semibold"
                      style={{ color: ep.alerts_count > 0 ? "var(--warn)" : "var(--tx-mute)" }}
                    >
                      {ep.alerts_count}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>
                    {ep.last_activity_ago ?? "Sin actividad registrada"}
                  </td>
                  <td className="py-2.5">
                    <button
                      onClick={() => onSelect(ep.id)}
                      className="flex items-center gap-1 text-[11.5px] font-medium border-0 bg-transparent cursor-pointer whitespace-nowrap"
                      style={{ color: "var(--brand)" }}
                    >
                      Detalles
                      <i className="ph ph-arrow-right text-[12px]" />
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
