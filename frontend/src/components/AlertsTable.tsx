import type { AlertListItem } from "../types/alerts";
import { severityPillStyle, SEVERITY_VAR } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  alerts: AlertListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
  selectedId: number | null;
  flashId: number | null;
}

function rowAccent(a: AlertListItem): string {
  if (a.severity === "CRÍTICO") return "var(--crit)";
  if (a.severity === "ALTO") return "var(--high)";
  if (a.severity === "MEDIO") return "var(--warn)";
  return "var(--brand)";
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-3 py-3.5">
          <div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 1 ? "78%" : "58%" }} />
        </td>
      ))}
    </tr>
  );
}

function RiskMeter({ score, color }: { score: number; color: string }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="min-w-[92px]">
      <div className="flex items-baseline gap-1.5">
        <span className="text-[12px] font-bold tabular-nums" style={{ color }}>{score.toFixed(1)}</span>
        <span className="text-[8.5px]" style={{ color: "var(--tx-mute)" }}>/ 100</span>
      </div>
      <div className="h-[3px] rounded-full overflow-hidden mt-1.5" style={{ background: "var(--surf3)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export default function AlertsTable({ alerts, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-list-bullets" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Cola operativa</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Detecciones registradas</div>
        </div>
        {!loading && (
          <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>
            {alerts.length} en esta página
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[1060px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Severidad</th>
              <th className="px-3 py-3 font-semibold">Detección</th>
              <th className="px-3 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Riesgo</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Fecha</th>
              <th className="px-3 py-3 font-semibold">Incidente</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 7 }).map((_, i) => <SkeletonRow key={i} />)
            ) : alerts.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: hasFilters ? "var(--brand-soft)" : "var(--ok-soft)", color: hasFilters ? "var(--brand)" : "var(--ok)" }}>
                    <i className={hasFilters ? "ph ph-magnifying-glass" : "ph ph-shield-check"} style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>
                    {hasFilters ? "Sin coincidencias" : "Sin alertas registradas"}
                  </div>
                  <div className="text-[9.5px] mt-1">
                    {hasFilters ? "Ajusta la búsqueda o elimina algunos filtros." : "Las nuevas detecciones aparecerán aquí automáticamente."}
                  </div>
                </td>
              </tr>
            ) : (
              alerts.map((a) => {
                const accent = rowAccent(a);
                const isSelected = a.id === selectedId;
                const isFlashing = a.id === flashId;
                const selStyle = rowSelectionStyle(isSelected, isFlashing);
                const critical = a.severity === "CRÍTICO";

                return (
                  <tr
                    key={a.id}
                    className="border-t cursor-pointer transition-premium"
                    style={{
                      borderColor: "var(--line-soft)",
                      ...selStyle,
                      boxShadow: `inset 3px 0 0 ${accent}`,
                    }}
                    onClick={() => onSelect(a.id)}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.background = critical ? "var(--crit-fill)" : "var(--surf2)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = (selStyle.background as string) || "transparent";
                    }}
                  >
                    <td className="px-4 py-3.5">
                      <span className="text-[9px] font-bold tracking-[.08em] px-2 py-1 rounded-md" style={severityPillStyle(a.severity)}>
                        {a.severity.toUpperCase()}
                      </span>
                    </td>

                    <td className="px-3 py-3.5 max-w-[320px]">
                      <div className="flex items-start gap-2.5">
                        <div
                          className="w-8 h-8 rounded-xl grid place-items-center shrink-0 mt-0.5"
                          style={{ background: `color-mix(in srgb, ${accent} 11%, var(--surf2))`, color: accent }}
                        >
                          <i className={critical ? "ph-fill ph-warning-octagon" : "ph ph-waveform"} style={{ fontSize: "14px" }} />
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold truncate" style={{ color: critical ? SEVERITY_VAR[a.severity] : "var(--tx)" }}>{a.title}</div>
                          <div className="flex items-center gap-2 mt-1 text-[9px]" style={{ color: "var(--tx-mute)" }}>
                            <span className="mono-data">ALR-{String(a.id).padStart(5, "0")}</span>
                            {a.rule_count > 0 && <><span>·</span><span>{a.rule_count === 1 ? "1 señal" : `${a.rule_count} señales`}</span></>}
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="w-7 h-7 rounded-lg grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                          <i className="ph ph-desktop-tower" style={{ fontSize: "12px" }} />
                        </span>
                        <span className="font-medium truncate max-w-[150px]" style={{ color: "var(--tx-dim)" }}>{a.hostname}</span>
                      </div>
                    </td>

                    <td className="px-3 py-3.5"><RiskMeter score={a.risk_score} color={accent} /></td>

                    <td className="px-3 py-3.5">
                      <span
                        className="inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-md"
                        style={{ ...statusPillStyle(a.status), border: `1px solid color-mix(in srgb, ${statusPillStyle(a.status).color} 35%, transparent)` }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusPillStyle(a.status).color }} />
                        {a.status_label}
                      </span>
                    </td>

                    <td className="px-3 py-3.5 whitespace-nowrap">
                      <div className="font-medium tabular-nums" style={{ color: "var(--tx-dim)" }}>{a.created_at}</div>
                    </td>

                    <td className="px-3 py-3.5">
                      {a.incident_id ? (
                        <a
                          href={`/incidentes/${a.incident_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 text-[9.5px] font-semibold no-underline px-2 py-1 rounded-lg"
                          style={{ color: "var(--brand)", background: "var(--brand-fill)", border: "1px solid var(--brand-soft)" }}
                        >
                          <i className="ph ph-siren" style={{ fontSize: "11px" }} />
                          INC-{String(a.incident_id).padStart(5, "0")}
                        </a>
                      ) : (
                        <span className="text-[9.5px]" style={{ color: "var(--tx-mute)" }}>Sin escalar</span>
                      )}
                    </td>

                    <td className="px-4 py-3.5 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelect(a.id); }}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover whitespace-nowrap"
                        style={{ background: "var(--brand-fill)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}
                        title="Ver detalles de la alerta"
                      >
                        <i className="ph ph-eye" style={{ fontSize: "13px" }} />
                        <span className="text-[10px] font-semibold">Ver detalles</span>
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
