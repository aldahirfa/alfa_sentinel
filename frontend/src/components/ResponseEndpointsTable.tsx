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

interface Props {
  items: ResponseEndpointItem[];
  loading: boolean;
  onChanged: () => void;
  onOpenDetail: (agentId: number) => void;
}

function statusPresentation(status: string | null) {
  if (status === "EXECUTED") {
    return { label: "Aislado", color: "var(--crit)", bg: "var(--crit-soft)", icon: "ph-fill ph-plugs" };
  }
  if (status === "REQUESTED") {
    return { label: "Aislamiento pendiente", color: "var(--warn)", bg: "var(--warn-soft)", icon: PENDING_ICON_CLASS };
  }
  if (status === "RELEASE_REQUESTED") {
    return { label: "Liberación pendiente", color: "var(--warn)", bg: "var(--warn-soft)", icon: PENDING_ICON_CLASS };
  }
  if (status === "ISOLATION_FAILED") {
    return { label: "Aislamiento fallido", color: "var(--crit)", bg: "var(--crit-soft)", icon: "ph-fill ph-warning-circle" };
  }
  return { label: "No aislado", color: "var(--ok)", bg: "var(--ok-soft)", icon: "ph-fill ph-check-circle" };
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
    if (!window.confirm(`¿Desaislar "${item.hostname}"?\n\nSe restaurará su conectividad de red cuando el agente confirme la orden.`)) return;
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
        <table className="w-full border-collapse text-[11px] min-w-[1120px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Sistema operativo</th>
              <th className="px-3 py-3 font-semibold">Agente</th>
              <th className="px-3 py-3 font-semibold">Contención</th>
              <th className="px-3 py-3 font-semibold">Última acción</th>
              <th className="px-3 py-3 font-semibold">Trazabilidad</th>
              <th className="px-4 py-3 font-semibold text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "65%" }} /></td>
                  ))}
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-14 text-center" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--surf3)", color: "var(--tx-dim)" }}>
                    <i className="ph ph-desktop" style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>No hay endpoints para mostrar</div>
                </td>
              </tr>
            ) : (
              filtered.map((item) => {
                const state = statusPresentation(item.isolation_status);
                const busy = workingId === item.agent_id;
                const pending = item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED";
                const isolated = item.isolation_status === "EXECUTED";
                return (
                  <tr key={item.agent_id} className="border-t transition-premium" style={{ borderColor: "var(--line-soft)" }}>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                          <i className="ph ph-desktop-tower" style={{ fontSize: "14px" }} />
                        </div>
                        <div>
                          <div className="text-[11.5px] font-bold" style={{ color: "var(--tx)" }}>{item.hostname}</div>
                          <div className="mono-data text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{item.ip_address}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="font-medium" style={{ color: "var(--tx-dim)" }}>{item.operating_system}</div>
                      {item.os_version && <div className="text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{item.os_version}</div>}
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-1.5 font-semibold" style={{ color: item.agent_status === "ONLINE" ? "var(--ok)" : "var(--tx-mute)" }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: item.agent_status === "ONLINE" ? "var(--ok)" : "var(--off)" }} />
                        {item.agent_status === "ONLINE" ? "Activo" : "Sin conexión"}
                      </div>
                      <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{item.last_seen_at ?? "Sin heartbeat"}</div>
                    </td>
                    <td className="px-3 py-3.5">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[9.5px] font-bold whitespace-nowrap" style={{ background: state.bg, color: state.color }}>
                        <i className={state.icon} />
                        {state.label}
                      </span>
                    </td>
                    <td className="px-3 py-3.5 max-w-[240px]" style={{ color: "var(--tx-dim)" }}>
                      <div className="text-[10px]">{latestActionLabel(item)}</div>
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="text-[10px] font-medium" style={{ color: "var(--tx-dim)" }}>{item.incident_count} incidente{item.incident_count === 1 ? "" : "s"}</div>
                      <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{item.isolation_count} acción{item.isolation_count === 1 ? "" : "es"} registrada{item.isolation_count === 1 ? "" : "s"}</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex justify-end items-center gap-2">
                        {pending ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-2 rounded-xl text-[10px] font-semibold" style={{ background: "var(--warn-soft)", color: "var(--warn)" }}>
                            <i className={PENDING_ICON_CLASS} /> En curso
                          </span>
                        ) : isolated ? (
                          <button
                            disabled={busy || !item.isolation_id}
                            onClick={() => handleRelease(item)}
                            title={RELEASE_TOOLTIP}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border text-[10px] font-bold cursor-pointer disabled:opacity-50 transition-premium btn-hover"
                            style={{ color: "var(--warn)", background: "var(--warn-soft)", borderColor: "var(--warn)" }}
                          >
                            <i className={busy ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} />
                            {busy ? "Enviando..." : "Desaislar"}
                          </button>
                        ) : (
                          <button
                            disabled={busy || !item.active_incident_id}
                            onClick={() => handleIsolate(item)}
                            title={item.active_incident_id ? ISOLATE_TOOLTIP : "No hay un incidente activo asociado a este endpoint."}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border text-[10px] font-bold cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed transition-premium btn-hover"
                            style={{ color: "var(--crit)", background: "var(--crit-soft)", borderColor: "var(--crit)" }}
                          >
                            <i className={busy ? SPINNER_ICON_CLASS : ISOLATE_ICON_CLASS} />
                            {busy ? "Enviando..." : "Aislar"}
                          </button>
                        )}

                        <button
                          onClick={() => onOpenDetail(item.agent_id)}
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover"
                          style={{ color: "var(--brand)", background: "var(--brand-fill)", borderColor: "var(--brand-soft)" }}
                        >
                          <i className="ph ph-eye" style={{ fontSize: "12px" }} />
                          <span className="text-[10px] font-semibold">Ver detalles</span>
                        </button>
                      </div>
                      {rowError?.id === item.agent_id && <div className="text-[9px] mt-1.5 max-w-[280px] ml-auto text-right" style={{ color: "var(--crit)" }}>{rowError.message}</div>}
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
