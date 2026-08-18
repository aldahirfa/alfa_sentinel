import { useState } from "react";
import type { CombinedItem } from "../types/incidentes";
import { severityPillStyle } from "../lib/severity";
import { statusBucketPillStyle } from "../lib/incidentStatus";
import { rowSelectionStyle } from "../lib/rowSelection";
import { isolateIncident } from "../api/client";
import {
  ISOLATE_ICON_CLASS, ISOLATED_ICON_CLASS, PENDING_ICON_CLASS, SPINNER_ICON_CLASS,
  ISOLATE_LABEL_COMPACT, ISOLATED_LABEL_COMPACT, PENDING_LABEL_COMPACT, SENDING_LABEL,
  ISOLATE_TOOLTIP, confirmIsolate,
  ISOLATE_BUTTON_CLASS_COMPACT, ISOLATE_BUTTON_STYLE_COMPACT,
} from "../lib/isolationUi";

interface Props {
  items: CombinedItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (item: CombinedItem) => void;
  // Claves "kind:id" -- ver IncidentesPage.tsx.
  selectedKey: string | null;
  flashKey: string | null;
  // Refresca /api/incidentes tras una orden manual exitosa (2026-08-17,
  // ver PENDIENTES.md, "Corrección de tiempo real, ordenamiento y
  // consistencia", sección 12) -- mismo criterio que
  // CriticalIncidentsTable.tsx (pantalla Respuesta): el estado real
  // vive en el servidor.
  onIsolated: () => void;
}

function rowAccent(item: CombinedItem): string | null {
  if (item.severity === "CRÍTICO") return "var(--crit)";
  if (item.severity === "ALTO") return "var(--high)";
  if (item.severity === "MEDIO") return "var(--warn)";
  return null;
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 9 }).map((_, i) => (
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

export default function IncidentesTable({ items, loading, hasFilters, onSelect, selectedKey, flashKey, onIsolated }: Props) {
  const [isolatingId, setIsolatingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  async function handleIsolate(e: React.MouseEvent, incidentId: number, hostname?: string | null) {
    e.stopPropagation();
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

  return (
    <section
      className="rounded-xl border p-5 overflow-x-auto shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-widest uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Código</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Regla</th>
            <th className="pb-2 pr-3 font-semibold">Severidad</th>
            <th className="pb-2 pr-3 font-semibold">Puntos de riesgo</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Responsable</th>
            <th className="pb-2 pr-3 font-semibold">Fecha</th>
            <th className="pb-2 font-semibold" style={{ minWidth: "170px" }} />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={9} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-magnifying-glass text-xl block mb-2" />
                {hasFilters
                  ? "Ningún incidente coincide con la búsqueda o los filtros aplicados."
                  : "Todavía no hay incidentes registrados."}
              </td>
            </tr>
          ) : (
            items.map((item) => {
              const accent = rowAccent(item);
              const key = `${item.kind}:${item.id}`;
              const isSelected = key === selectedKey;
              const isFlashing = key === flashKey;
              const selStyle = rowSelectionStyle(isSelected, isFlashing);
              return (
                <tr
                  key={key}
                  className="border-t transition-colors cursor-pointer group"
                  style={{ borderColor: "var(--line-soft)", ...selStyle }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = selStyle.background as string)}
                >
                  <td className="py-3 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <div className="flex items-center gap-1.5 pl-2">
                      <i className="ph-fill ph-siren" style={{ fontSize: "13px", color: "var(--tx-mute)" }} />
                      <span className="font-bold tracking-tight" style={{ color: "var(--tx)" }}>{item.code}</span>
                    </div>
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>
                    <span className="truncate block max-w-[160px]">{item.rule_label}</span>
                  </td>
                  <td className="py-3 pr-3">
                    {item.severity ? (
                      <span
                        className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full"
                        style={severityPillStyle(item.severity)}
                      >
                        {item.severity.toUpperCase()}
                      </span>
                    ) : (
                      <span style={{ color: "var(--tx-mute)" }}>—</span>
                    )}
                  </td>
                  <td className="py-3 pr-3 tabular-nums font-bold" style={{ color: "var(--tx)" }}>
                    {item.risk_score !== null ? item.risk_score.toFixed(1) : "—"}
                  </td>
                  <td className="py-3 pr-3">
                    <span
                      className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full w-fit inline-block"
                      style={{ ...statusBucketPillStyle(item.status_bucket), border: `1px solid ${statusBucketPillStyle(item.status_bucket).color}` }}
                    >
                      {item.status_label}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: item.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>
                    {item.assigned_to_name ?? "Sin asignar"}
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.created_at}</td>
                  <td className="py-3">
                    <div className="flex flex-col items-end gap-1">
                      <div className="flex items-center gap-2.5 justify-end">
                        {item.kind !== "incident" ? null : item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED" ? (
                          <span className="flex items-center gap-1.5 text-[11.5px] font-bold px-2 py-1 whitespace-nowrap" style={{ color: "var(--warn)" }}>
                            <i className={`${PENDING_ICON_CLASS} text-[13px]`} />
                            {PENDING_LABEL_COMPACT}
                          </span>
                        ) : item.isolation_status === "EXECUTED" ? (
                          <span className="flex items-center gap-1.5 text-[11.5px] font-bold px-2 py-1 whitespace-nowrap" style={{ color: "var(--crit)" }}>
                            <i className={`${ISOLATED_ICON_CLASS} text-[13px]`} />
                            {ISOLATED_LABEL_COMPACT}
                          </span>
                        ) : (
                          <button
                            disabled={isolatingId === item.id}
                            onClick={(e) => handleIsolate(e, item.id, item.hostname)}
                            title={ISOLATE_TOOLTIP}
                            className={ISOLATE_BUTTON_CLASS_COMPACT}
                            style={ISOLATE_BUTTON_STYLE_COMPACT}
                          >
                            <i className={isolatingId === item.id ? `${SPINNER_ICON_CLASS} text-[13px]` : `${ISOLATE_ICON_CLASS} text-[13px]`} />
                            {isolatingId === item.id ? SENDING_LABEL : ISOLATE_LABEL_COMPACT}
                          </button>
                        )}
                        <button
                          onClick={() => onSelect(item)}
                          className="flex items-center gap-1.5 text-[11.5px] font-bold border-0 bg-transparent cursor-pointer whitespace-nowrap transition-premium btn-hover"
                          style={{ color: "var(--brand)" }}
                        >
                          Ver más detalles
                          <i className="ph-fill ph-arrow-right text-[13px]" />
                        </button>
                      </div>
                      {rowError?.id === item.id && (
                        <div className="text-[10px]" style={{ color: "var(--crit)" }}>{rowError.message}</div>
                      )}
                    </div>
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
