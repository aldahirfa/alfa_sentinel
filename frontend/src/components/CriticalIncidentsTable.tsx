import { useState } from "react";
import type { CriticalIncidentItem } from "../types/respuesta";
import { severityPillStyle } from "../lib/severity";
import { isolateIncident, releaseIsolation } from "../api/client";
import {
  ISOLATE_ICON_CLASS, ISOLATED_ICON_CLASS, RELEASE_ICON_CLASS, PENDING_ICON_CLASS, SPINNER_ICON_CLASS,
  ISOLATE_LABEL_COMPACT, ISOLATED_LABEL_COMPACT, RELEASE_LABEL_COMPACT, PENDING_LABEL_COMPACT, SENDING_LABEL,
  ISOLATE_TOOLTIP, RELEASE_TOOLTIP, confirmIsolate,
  ISOLATE_BUTTON_CLASS_COMPACT, ISOLATE_BUTTON_STYLE_COMPACT,
} from "../lib/isolationUi";

interface Props {
  items: CriticalIncidentItem[];
  loading: boolean;
  onIsolated: () => void;
}

export default function CriticalIncidentsTable({ items, loading, onIsolated }: Props) {
  const [isolatingId, setIsolatingId] = useState<number | null>(null);
  const [releasingId, setReleasingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  async function handleIsolate(incidentId: number, hostname?: string | null) {
    if (!confirmIsolate(hostname)) return;
    setIsolatingId(incidentId);
    setRowError(null);
    try {
      await isolateIncident(incidentId);
      onIsolated();
    } catch (err) {
      setRowError({ id: incidentId, message: err instanceof Error ? err.message : "No se pudo enviar la orden." });
    } finally {
      setIsolatingId(null);
    }
  }

  async function handleRelease(isolationId: number, rowKey: number) {
    setReleasingId(rowKey);
    setRowError(null);
    try {
      await releaseIsolation(isolationId);
      onIsolated();
    } catch (err) {
      setRowError({ id: rowKey, message: err instanceof Error ? err.message : "No se pudo enviar la orden de liberación." });
    } finally {
      setReleasingId(null);
    }
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          <i className="ph ph-shield-warning" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Respuesta operativa</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Incidentes que requieren atención</div>
        </div>
        {!loading && (
          <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: items.length > 0 ? "var(--crit-soft)" : "var(--surf3)", color: items.length > 0 ? "var(--crit)" : "var(--tx-mute)" }}>
            {items.length} {items.length === 1 ? "caso" : "casos"}
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[1120px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Código</th>
              <th className="px-3 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Severidad</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Responsable</th>
              <th className="px-3 py-3 font-semibold">Abierto</th>
              <th className="px-3 py-3 font-semibold">Aislamiento</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "62%" }} /></td>
                  ))}
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
                    <i className="ph-fill ph-shield-check" style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>Sin casos prioritarios pendientes</div>
                  <div className="text-[9.5px] mt-1">No hay incidentes de severidad alta o crítica que requieran una acción manual.</div>
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={item.id}
                  className="border-t transition-premium"
                  style={{ borderColor: "var(--line-soft)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td className="px-4 py-3.5 font-semibold" style={item.severity === "CRÍTICO" ? { boxShadow: "inset 3px 0 0 var(--crit)" } : undefined}>
                    <span className="font-bold" style={{ color: "var(--tx)" }}>{item.code}</span>
                    <div className="text-[9px] mt-1 font-medium truncate max-w-[190px]" style={{ color: "var(--tx-mute)" }}>{item.title}</div>
                  </td>
                  <td className="px-3 py-3.5 font-medium" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                  <td className="px-3 py-3.5">
                    {item.severity && <span className="text-[9px] font-bold tracking-wide px-2 py-1 rounded-md" style={severityPillStyle(item.severity)}>{item.severity.toUpperCase()}</span>}
                  </td>
                  <td className="px-3 py-3.5 font-semibold" style={{ color: "var(--tx-dim)" }}>{item.status_label}</td>
                  <td className="px-3 py-3.5" style={{ color: item.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>{item.assigned_to_name ?? "Sin asignar"}</td>
                  <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.opened_at}</td>
                  <td className="px-3 py-3.5">
                    {item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED" ? (
                      <span className="text-[10px] font-semibold whitespace-nowrap" style={{ color: "var(--warn)" }}><i className={`${PENDING_ICON_CLASS} mr-1`} />{PENDING_LABEL_COMPACT}</span>
                    ) : item.isolation_status === "EXECUTED" ? (
                      <div className="flex items-center gap-2.5">
                        <span className="text-[10px] font-semibold whitespace-nowrap" style={{ color: "var(--crit)" }}><i className={`${ISOLATED_ICON_CLASS} mr-1`} />{ISOLATED_LABEL_COMPACT}</span>
                        {item.isolation_id && (
                          <button
                            disabled={releasingId === item.id}
                            onClick={(e) => { e.stopPropagation(); handleRelease(item.isolation_id!, item.id); }}
                            title={RELEASE_TOOLTIP}
                            className="flex items-center gap-1.5 text-[10px] font-semibold whitespace-nowrap cursor-pointer border-0 bg-transparent disabled:opacity-50 transition-premium btn-hover"
                            style={{ color: "var(--warn)" }}
                          >
                            <i className={releasingId === item.id ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} />
                            {releasingId === item.id ? SENDING_LABEL : RELEASE_LABEL_COMPACT}
                          </button>
                        )}
                      </div>
                    ) : (
                      <button disabled={isolatingId === item.id} onClick={(e) => { e.stopPropagation(); handleIsolate(item.id, item.hostname); }} title={ISOLATE_TOOLTIP} className={ISOLATE_BUTTON_CLASS_COMPACT} style={ISOLATE_BUTTON_STYLE_COMPACT}>
                        <i className={isolatingId === item.id ? SPINNER_ICON_CLASS : ISOLATE_ICON_CLASS} />
                        {isolatingId === item.id ? SENDING_LABEL : ISOLATE_LABEL_COMPACT}
                      </button>
                    )}
                    {rowError?.id === item.id && <div className="text-[9px] mt-1" style={{ color: "var(--crit)" }}>{rowError.message}</div>}
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <a href={`/incidentes/${item.id}`} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border no-underline whitespace-nowrap transition-premium btn-hover" style={{ color: "var(--brand)", background: "var(--brand-fill)", borderColor: "var(--brand-soft)" }}>
                      <span className="text-[10px] font-semibold">Ver incidente</span>
                      <i className="ph ph-arrow-right" style={{ fontSize: "12px" }} />
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
