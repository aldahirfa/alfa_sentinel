import type { EndpointListItem } from "../types/endpoints";
import { severityPillStyle, SEVERITY_VAR } from "../lib/severity";
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

function accentOf(ep: EndpointListItem): string {
  if (ep.risk === "CRÍTICO" || ep.conn_status === "ISOLATED") return "var(--crit)";
  if (ep.risk === "ALTO") return "var(--high)";
  if (ep.risk === "MEDIO") return "var(--warn)";
  return "var(--brand)";
}

function osIcon(os: string): string {
  const value = os.toLowerCase();
  if (value.includes("win")) return "ph-fill ph-windows-logo";
  if (value.includes("linux") || value.includes("ubuntu") || value.includes("debian")) return "ph-fill ph-linux-logo";
  return "ph-fill ph-desktop";
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-3 py-3.5">
          <div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 0 ? "76%" : "56%" }} />
        </td>
      ))}
    </tr>
  );
}

export default function EndpointsTable({ endpoints, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-desktop-tower" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Inventario protegido</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Endpoints monitoreados</div>
        </div>
        {!loading && <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{endpoints.length} en esta página</div>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[1100px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Conectividad</th>
              <th className="px-3 py-3 font-semibold">Riesgo</th>
              <th className="px-3 py-3 font-semibold">Agente</th>
              <th className="px-3 py-3 font-semibold">Última conexión</th>
              <th className="px-3 py-3 font-semibold">Alertas</th>
              <th className="px-3 py-3 font-semibold">Actividad</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 7 }).map((_, i) => <SkeletonRow key={i} />)
            ) : endpoints.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: hasFilters ? "var(--brand-soft)" : "var(--ok-soft)", color: hasFilters ? "var(--brand)" : "var(--ok)" }}>
                    <i className={hasFilters ? "ph ph-magnifying-glass" : "ph ph-desktop-tower"} style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>{hasFilters ? "Sin coincidencias" : "Sin endpoints registrados"}</div>
                  <div className="text-[9.5px] mt-1">{hasFilters ? "Ajusta los filtros para ampliar la búsqueda." : "Los agentes enrolados aparecerán aquí automáticamente."}</div>
                </td>
              </tr>
            ) : (
              endpoints.map((ep) => {
                const accent = accentOf(ep);
                const isSelected = ep.id === selectedId;
                const selStyle = rowSelectionStyle(isSelected, ep.id === flashId);
                const critical = ep.risk === "CRÍTICO" || ep.conn_status === "ISOLATED";

                return (
                  <tr
                    key={ep.id}
                    className="border-t cursor-pointer transition-premium"
                    style={{ borderColor: "var(--line-soft)", ...selStyle, boxShadow: `inset 3px 0 0 ${accent}` }}
                    onClick={() => onSelect(ep.id)}
                    onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = critical ? "var(--crit-fill)" : "var(--surf2)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = (selStyle.background as string) || "transparent"; }}
                  >
                    <td className="px-4 py-3.5 min-w-[260px]">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: `color-mix(in srgb, ${accent} 11%, var(--surf2))`, color: accent }}>
                          <i className={osIcon(ep.operating_system)} style={{ fontSize: "16px" }} />
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold truncate" style={{ color: "var(--tx)" }}>{ep.hostname}</div>
                          <div className="flex items-center gap-2 mt-1 text-[9px]" style={{ color: "var(--tx-mute)" }}>
                            <span>{ep.operating_system} {ep.os_version}</span>
                            <span>·</span>
                            <span className="mono-data">{ep.ip_address}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-3.5">
                      <span className="inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-md" style={{ ...connStatusPillStyle(ep.conn_status), border: `1px solid ${connStatusPillStyle(ep.conn_status).color}` }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[ep.conn_status] }} />
                        {CONN_STATUS_LABEL[ep.conn_status]}
                      </span>
                    </td>

                    <td className="px-3 py-3.5">
                      <span className="text-[9px] font-bold tracking-[.08em] px-2 py-1 rounded-md" style={severityPillStyle(ep.risk)}>{ep.risk.toUpperCase()}</span>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ background: AGENT_HEALTH_VAR[ep.agent_health], boxShadow: `0 0 0 3px color-mix(in srgb, ${AGENT_HEALTH_VAR[ep.agent_health]} 14%, transparent)` }} />
                        <span className="text-[10px] font-medium" style={{ color: "var(--tx-dim)" }}>{AGENT_HEALTH_LABEL[ep.agent_health]}</span>
                      </div>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="text-[10px] font-medium" style={{ color: "var(--tx-dim)" }}>{ep.last_seen_ago}</div>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-bold tabular-nums" style={{ color: ep.alerts_count > 0 ? "var(--warn)" : "var(--tx)" }}>{ep.alerts_count}</span>
                        <span className="text-[9px]" style={{ color: "var(--tx-mute)" }}>activas</span>
                      </div>
                    </td>

                    <td className="px-3 py-3.5 max-w-[190px]">
                      <div className="text-[9.5px] truncate" style={{ color: "var(--tx-mute)" }}>{ep.last_activity_ago ?? "Sin actividad registrada"}</div>
                    </td>

                    <td className="px-4 py-3.5 text-right">
                      <button onClick={(e) => { e.stopPropagation(); onSelect(ep.id); }} className="w-8 h-8 rounded-xl border grid place-items-center ml-auto cursor-pointer transition-premium btn-hover" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)", color: "var(--brand)" }} title="Abrir ficha del endpoint">
                        <i className="ph ph-arrow-up-right" style={{ fontSize: "13px" }} />
                      </button>
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
