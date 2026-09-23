import { useMemo, useState } from "react";
import type { ResponseEndpointItem } from "../types/respuesta";
import { isolateIncident, releaseIsolation } from "../api/client";
import {
  ISOLATE_ICON_CLASS,
  RELEASE_ICON_CLASS,
  PENDING_ICON_CLASS,
  SPINNER_ICON_CLASS,
  ISOLATE_TOOLTIP,
  RELEASE_TOOLTIP,
  confirmIsolate,
} from "../lib/isolationUi";
import {
  CONN_STATUS_LABEL,
  CONN_STATUS_VAR,
  connStatusPillStyle,
} from "../lib/endpointStatus";

interface Props {
  items: ResponseEndpointItem[];
  loading: boolean;
  onChanged: () => void;
  onOpenDetail: (agentId: number) => void;
}

function osIcon(os: string): string {
  const value = os.toLowerCase();
  if (value.includes("win")) return "ph-fill ph-windows-logo";
  if (value.includes("linux") || value.includes("ubuntu") || value.includes("debian")) return "ph-fill ph-linux-logo";
  return "ph-fill ph-desktop";
}

function endpointAccent(item: ResponseEndpointItem): string {
  if (item.isolation_status === "EXECUTED" || item.isolation_status === "ISOLATION_FAILED") return "var(--crit)";
  if (item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED") return "var(--warn)";
  return "var(--brand)";
}

function latestActionLabel(item: ResponseEndpointItem) {
  if (!item.latest_action_at) return "Sin acciones registradas";
  if (item.isolation_status === "EXECUTED") return `Aislado · ${item.latest_action_at}`;
  if (item.isolation_status === "REQUESTED") return `Aislamiento solicitado · ${item.latest_action_at}`;
  if (item.isolation_status === "RELEASE_REQUESTED") return `Liberación solicitada · ${item.latest_action_at}`;
  if (item.isolation_status === "RELEASED") return `Liberado · ${item.latest_action_at}`;
  if (item.isolation_status === "ISOLATION_FAILED") return `Aislamiento fallido · ${item.latest_action_at}`;
  return item.latest_action_at;
}

const actionButtonClass =
  "inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover whitespace-nowrap disabled:opacity-45 disabled:cursor-not-allowed";

export default function ResponseEndpointsTable({ items, loading, onChanged, onOpenDetail }: Props) {
  const [search, setSearch] = useState("");
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) =>
      item.hostname.toLowerCase().includes(q) ||
      item.ip_address.toLowerCase().includes(q) ||
      item.operating_system.toLowerCase().includes(q)
    );
  }, [items, search]);

  async function handleIsolate(item: ResponseEndpointItem) {
    if (!item.active_incident_id) {
      setRowError({ id: item.agent_id, message: "Este endpoint no tiene un incidente activo al cual asociar la contención." });
      return;
    }
    if (!confirmIsolate(item.hostname)) return;
    setWorkingId(item.agent_id);
    setRowError(null);
    try {
      await isolateIncident(item.active_incident_id);
      onChanged();
    } catch (err) {
      setRowError({ id: item.agent_id, message: err instanceof Error ? err.message : "No se pudo enviar la orden de aislamiento." });
    } finally {
      setWorkingId(null);
    }
  }

  async function handleRelease(item: ResponseEndpointItem) {
    if (!item.isolation_id) return;
    if (!window.confirm(`¿Liberar "${item.hostname}"?\n\nSe restaurará su conectividad de red cuando el agente confirme la orden.`)) return;
    setWorkingId(item.agent_id);
    setRowError(null);
    try {
      await releaseIsolation(item.isolation_id);
      onChanged();
    } catch (err) {
      setRowError({ id: item.agent_id, message: err instanceof Error ? err.message : "No se pudo enviar la orden de liberación." });
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex flex-col lg:flex-row lg:items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
            <i className="ph ph-desktop-tower" style={{ fontSize: "17px" }} />
          </div>
          <div>
            <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Control operativo</div>
            <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Endpoints registrados</div>
          </div>
        </div>

        <div className="lg:ml-auto relative w-full lg:w-[310px]">
          <i className="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--tx-mute)", fontSize: "13px" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar endpoint, IP o sistema operativo"
            className="w-full pl-9 pr-3 py-2.5 rounded-xl text-[11px] outline-none"
            style={{ background: "var(--surf2)", color: "var(--tx)", border: "1px solid var(--line)" }}
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[900px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Conectividad</th>
              <th className="px-3 py-3 font-semibold">Última acción</th>
              <th className="px-3 py-3 font-semibold">Trazabilidad</th>
              <th className="px-4 py-3 font-semibold text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: j === 0 ? "76%" : "60%" }} /></td>
                  ))}
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-14 text-center" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--surf3)", color: "var(--tx-dim)" }}>
                    <i className="ph ph-desktop" style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>No hay endpoints para mostrar</div>
                </td>
              </tr>
            ) : (
              filtered.map((item) => {
                const busy = workingId === item.agent_id;
                const pending = item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED";
                const isolated = item.isolation_status === "EXECUTED";
                const accent = endpointAccent(item);
                const connectivity = item.agent_status === "ONLINE" ? "ONLINE" : "OFFLINE";

                return (
                  <tr
                    key={item.agent_id}
                    className="border-t transition-premium"
                    style={{ borderColor: "var(--line-soft)", boxShadow: `inset 3px 0 0 ${accent}` }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--surf2)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <td className="px-4 py-3.5 min-w-[300px]">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-9 h-9 rounded-xl grid place-items-center shrink-0"
                          style={{ background: `color-mix(in srgb, ${accent} 11%, var(--surf2))`, color: accent }}
                        >
                          <i className={osIcon(item.operating_system)} style={{ fontSize: "16px" }} />
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold truncate" style={{ color: "var(--tx)" }}>{item.hostname}</div>
                          <div className="flex items-center gap-2 mt-1 text-[9px]" style={{ color: "var(--tx-mute)" }}>
                            <span>{item.operating_system}{item.os_version ? ` ${item.os_version}` : ""}</span>
                            <span>·</span>
                            <span className="mono-data">{item.ip_address}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-3.5">
                      <span
                        className="inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-md"
                        style={{ ...connStatusPillStyle(connectivity), border: `1px solid ${connStatusPillStyle(connectivity).color}` }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[connectivity] }} />
                        {CONN_STATUS_LABEL[connectivity]}
                      </span>
                      <div className="text-[9px] mt-1.5" style={{ color: "var(--tx-mute)" }}>{item.last_seen_at ?? "Sin heartbeat"}</div>
                    </td>

                    <td className="px-3 py-3.5 max-w-[250px]" style={{ color: "var(--tx-dim)" }}>
                      <div className="text-[10px]">{latestActionLabel(item)}</div>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="text-[10px] font-medium" style={{ color: "var(--tx-dim)" }}>{item.incident_count} incidente{item.incident_count === 1 ? "" : "s"}</div>
                      <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{item.isolation_count} acción{item.isolation_count === 1 ? "" : "es"} registrada{item.isolation_count === 1 ? "" : "s"}</div>
                    </td>

                    <td className="px-4 py-3.5">
                      <div className="flex justify-end items-center gap-2">
                        {pending ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-2 text-[10px] font-semibold whitespace-nowrap" style={{ color: "var(--warn)" }}>
                            <i className={PENDING_ICON_CLASS} style={{ fontSize: "13px" }} />
                            En curso
                          </span>
                        ) : isolated ? (
                          <button
                            disabled={busy || !item.isolation_id}
                            onClick={() => handleRelease(item)}
                            title={RELEASE_TOOLTIP}
                            className={actionButtonClass}
                            style={{ color: "var(--warn)", background: "var(--warn-fill)", borderColor: "var(--warn-soft)" }}
                          >
                            <i className={busy ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} style={{ fontSize: "13px" }} />
                            <span className="text-[10px] font-semibold">{busy ? "Enviando..." : "Liberar"}</span>
                          </button>
                        ) : (
                          <button
                            disabled={busy || !item.active_incident_id}
                            onClick={() => handleIsolate(item)}
                            title={item.active_incident_id ? ISOLATE_TOOLTIP : "No hay un incidente activo asociado a este endpoint."}
                            className={actionButtonClass}
                            style={{ color: "var(--crit)", background: "var(--crit-fill)", borderColor: "var(--crit-soft)" }}
                          >
                            <i className={busy ? SPINNER_ICON_CLASS : ISOLATE_ICON_CLASS} style={{ fontSize: "13px" }} />
                            <span className="text-[10px] font-semibold">{busy ? "Enviando..." : "Aislar"}</span>
                          </button>
                        )}

                        <button
                          onClick={() => onOpenDetail(item.agent_id)}
                          className={actionButtonClass}
                          style={{ color: "var(--brand)", background: "var(--brand-fill)", borderColor: "var(--brand-soft)" }}
                          title="Ver incidentes e historial de respuesta del endpoint"
                        >
                          <i className="ph ph-eye" style={{ fontSize: "13px" }} />
                          <span className="text-[10px] font-semibold">Ver detalles</span>
                        </button>
                      </div>

                      {rowError?.id === item.agent_id && (
                        <div className="text-[9px] mt-1.5 max-w-[280px] ml-auto text-right" style={{ color: "var(--crit)" }}>
                          {rowError.message}
                        </div>
                      )}
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
