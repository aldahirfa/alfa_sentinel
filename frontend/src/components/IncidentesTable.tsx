import { useState } from "react";
import type { CombinedItem } from "../types/incidentes";
import { severityPillStyle, SEVERITY_VAR } from "../lib/severity";
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
  selectedKey: string | null;
  flashKey: string | null;
  onIsolated: () => void;
}

function accentOf(item: CombinedItem): string {
  if (item.severity === "CRÍTICO") return "var(--crit)";
  if (item.severity === "ALTO") return "var(--high)";
  if (item.severity === "MEDIO") return "var(--warn)";
  return "var(--brand)";
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-3 py-3.5">
          <div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 1 ? "76%" : "56%" }} />
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
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph-fill ph-siren" style={{ fontSize: "16px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Centro de casos</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Incidentes y alertas escaladas</div>
        </div>
        {!loading && <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{items.length} en esta página</div>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[1120px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Caso</th>
              <th className="px-3 py-3 font-semibold">Endpoint / detección</th>
              <th className="px-3 py-3 font-semibold">Severidad</th>
              <th className="px-3 py-3 font-semibold">Riesgo</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Responsable</th>
              <th className="px-3 py-3 font-semibold">Fecha</th>
              <th className="px-4 py-3 font-semibold text-right">Respuesta</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 7 }).map((_, i) => <SkeletonRow key={i} />)
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: hasFilters ? "var(--brand-soft)" : "var(--ok-soft)", color: hasFilters ? "var(--brand)" : "var(--ok)" }}>
                    <i className={hasFilters ? "ph ph-magnifying-glass" : "ph ph-shield-check"} style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>{hasFilters ? "Sin coincidencias" : "Sin incidentes activos"}</div>
                  <div className="text-[9.5px] mt-1">{hasFilters ? "Ajusta los filtros para ampliar la búsqueda." : "Los nuevos casos aparecerán aquí cuando sean escalados."}</div>
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const accent = accentOf(item);
                const key = `${item.kind}:${item.id}`;
                const isSelected = key === selectedKey;
                const selStyle = rowSelectionStyle(isSelected, key === flashKey);
                const critical = item.severity === "CRÍTICO";

                return (
                  <tr
                    key={key}
                    className="border-t cursor-pointer transition-premium"
                    style={{ borderColor: "var(--line-soft)", ...selStyle, boxShadow: `inset 3px 0 0 ${accent}` }}
                    onClick={() => onSelect(item)}
                    onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = critical ? "var(--crit-fill)" : "var(--surf2)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = (selStyle.background as string) || "transparent"; }}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: `color-mix(in srgb, ${accent} 11%, var(--surf2))`, color: accent }}>
                          <i className="ph-fill ph-siren" style={{ fontSize: "14px" }} />
                        </div>
                        <div>
                          <div className="mono-data text-[10.5px] font-bold" style={{ color: "var(--tx)" }}>{item.code}</div>
                          <div className="text-[8.5px] mt-1" style={{ color: "var(--tx-mute)" }}>{item.kind === "incident" ? "Incidente" : "Alerta pendiente"}</div>
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-3.5 max-w-[280px]">
                      <div className="flex items-center gap-2">
                        <i className="ph ph-desktop-tower" style={{ fontSize: "12px", color: "var(--brand)" }} />
                        <span className="font-semibold truncate" style={{ color: "var(--tx)" }}>{item.hostname}</span>
                        <span className="mono-data text-[8.5px]" style={{ color: "var(--tx-mute)" }}>{item.ip_address}</span>
                      </div>
                      <div className="text-[9px] mt-1.5 truncate" style={{ color: "var(--tx-mute)" }}>{item.rule_label} · {item.detection_count} señal{item.detection_count === 1 ? "" : "es"}</div>
                    </td>

                    <td className="px-3 py-3.5">
                      {item.severity ? <span className="text-[9px] font-bold tracking-[.08em] px-2 py-1 rounded-md" style={severityPillStyle(item.severity)}>{item.severity.toUpperCase()}</span> : <span style={{ color: "var(--tx-mute)" }}>—</span>}
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="text-[12px] font-bold tabular-nums" style={{ color: item.severity ? SEVERITY_VAR[item.severity] : "var(--tx)" }}>{item.risk_score !== null ? item.risk_score.toFixed(1) : "—"}</div>
                    </td>

                    <td className="px-3 py-3.5">
                      <span className="inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-md" style={{ ...statusBucketPillStyle(item.status_bucket), border: `1px solid ${statusBucketPillStyle(item.status_bucket).color}` }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusBucketPillStyle(item.status_bucket).color }} />
                        {item.status_label}
                      </span>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="w-7 h-7 rounded-full grid place-items-center text-[9px] font-bold" style={{ background: item.assigned_to_name ? "var(--brand-soft)" : "var(--surf3)", color: item.assigned_to_name ? "var(--brand)" : "var(--tx-mute)" }}>
                          {item.assigned_to_name ? item.assigned_to_name.slice(0, 1).toUpperCase() : "?"}
                        </span>
                        <span className="text-[10px]" style={{ color: item.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>{item.assigned_to_name ?? "Sin asignar"}</span>
                      </div>
                    </td>

                    <td className="px-3 py-3.5 whitespace-nowrap text-[9.5px] tabular-nums" style={{ color: "var(--tx-dim)" }}>{item.created_at}</td>

                    <td className="px-4 py-3.5">
                      <div className="flex flex-col items-end gap-1.5">
                        <div className="flex items-center gap-2 justify-end">
                          {item.kind === "incident" && (
                            item.isolation_status === "REQUESTED" || item.isolation_status === "RELEASE_REQUESTED" ? (
                              <span className="flex items-center gap-1.5 text-[9.5px] font-bold px-2 py-1 whitespace-nowrap" style={{ color: "var(--warn)" }}><i className={`${PENDING_ICON_CLASS} text-[12px]`} />{PENDING_LABEL_COMPACT}</span>
                            ) : item.isolation_status === "EXECUTED" ? (
                              <span className="flex items-center gap-1.5 text-[9.5px] font-bold px-2 py-1 whitespace-nowrap" style={{ color: "var(--crit)" }}><i className={`${ISOLATED_ICON_CLASS} text-[12px]`} />{ISOLATED_LABEL_COMPACT}</span>
                            ) : (
                              <button disabled={isolatingId === item.id} onClick={(e) => handleIsolate(e, item.id, item.hostname)} title={ISOLATE_TOOLTIP} className={ISOLATE_BUTTON_CLASS_COMPACT} style={ISOLATE_BUTTON_STYLE_COMPACT}>
                                <i className={isolatingId === item.id ? `${SPINNER_ICON_CLASS} text-[12px]` : `${ISOLATE_ICON_CLASS} text-[12px]`} />
                                {isolatingId === item.id ? SENDING_LABEL : ISOLATE_LABEL_COMPACT}
                              </button>
                            )
                          )}
                          <button onClick={(e) => { e.stopPropagation(); onSelect(item); }} className="w-8 h-8 rounded-xl border grid place-items-center cursor-pointer transition-premium btn-hover" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)", color: "var(--brand)" }} title="Abrir investigación">
                            <i className="ph ph-arrow-up-right" style={{ fontSize: "13px" }} />
                          </button>
                        </div>
                        {rowError?.id === item.id && <div className="text-[9px] max-w-[190px] text-right" style={{ color: "var(--crit)" }}>{rowError.message}</div>}
                      </div>
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
