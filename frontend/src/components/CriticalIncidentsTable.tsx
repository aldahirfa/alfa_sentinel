import { useState } from "react";
import type { CriticalIncidentItem } from "../types/respuesta";
import { severityPillStyle } from "../lib/severity";
import { isolateIncident, releaseIsolation } from "../api/client";
import {
  ISOLATE_ICON_CLASS, ISOLATED_ICON_CLASS, RELEASE_ICON_CLASS, PENDING_ICON_CLASS, SPINNER_ICON_CLASS,
  ISOLATE_LABEL_COMPACT, ISOLATED_LABEL_COMPACT, RELEASE_LABEL_COMPACT, PENDING_LABEL_COMPACT, SENDING_LABEL,
  ISOLATE_TOOLTIP, RELEASE_TOOLTIP, confirmIsolate,
} from "../lib/isolationUi";

interface Props {
  items: CriticalIncidentItem[];
  loading: boolean;
  // Refresca /api/respuesta después de una orden manual exitosa --
  // el estado real (REQUESTED) vive en el servidor, no se optimiza
  // localmente (2026-08-17, ver PENDIENTES.md, "Aislamiento de host --
  // modo development, laboratorio y producción").
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

  // Mismo backend/máquina de estados que el botón "Liberar" de
  // IsolationsHistoryTable.tsx y del drawer -- una sola implementación
  // (sección 13 de "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO REAL...",
  // 2026-08-17, ver PENDIENTES.md).
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
            <th className="pb-2 pr-3 font-semibold">Aislamiento</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 8 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={8} className="text-center py-8" style={{ color: "var(--tx-mute)" }}>
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
                <td className="py-3 pr-3">
                  {item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED" ? (
                    <span className="text-[11px] font-bold whitespace-nowrap" style={{ color: "var(--warn)" }}>
                      <i className={`${PENDING_ICON_CLASS} mr-1`} />
                      {PENDING_LABEL_COMPACT}
                    </span>
                  ) : item.isolation_status === "EXECUTED" ? (
                    <div className="flex items-center gap-2.5">
                      <span className="text-[11px] font-bold whitespace-nowrap" style={{ color: "var(--crit)" }}>
                        <i className={`${ISOLATED_ICON_CLASS} mr-1`} />
                        {ISOLATED_LABEL_COMPACT}
                      </span>
                      {item.isolation_id && (
                        // Amarillo, nunca rojo (sección 11) -- Liberar
                        // es lo opuesto de Aislar, no una acción de
                        // riesgo.
                        <button
                          disabled={releasingId === item.id}
                          onClick={(e) => { e.stopPropagation(); handleRelease(item.isolation_id!, item.id); }}
                          title={RELEASE_TOOLTIP}
                          className="flex items-center gap-1.5 text-[11.5px] font-bold whitespace-nowrap cursor-pointer border-0 bg-transparent disabled:opacity-50 transition-premium btn-hover"
                          style={{ color: "var(--warn)" }}
                        >
                          <i className={releasingId === item.id ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} />
                          {releasingId === item.id ? SENDING_LABEL : RELEASE_LABEL_COMPACT}
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      disabled={isolatingId === item.id}
                      onClick={(e) => { e.stopPropagation(); handleIsolate(item.id, item.hostname); }}
                      title={ISOLATE_TOOLTIP}
                      className="flex items-center gap-1.5 text-[11.5px] font-bold whitespace-nowrap cursor-pointer border-0 bg-transparent disabled:opacity-50 transition-premium btn-hover"
                      style={{ color: "var(--crit)" }}
                    >
                      <i className={isolatingId === item.id ? SPINNER_ICON_CLASS : ISOLATE_ICON_CLASS} />
                      {isolatingId === item.id ? SENDING_LABEL : ISOLATE_LABEL_COMPACT}
                    </button>
                  )}
                  {rowError?.id === item.id && (
                    <div className="text-[10px] mt-1" style={{ color: "var(--crit)" }}>{rowError.message}</div>
                  )}
                </td>
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
