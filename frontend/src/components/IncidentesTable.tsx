import type { CombinedItem } from "../types/incidentes";
import { severityPillStyle } from "../lib/severity";
import { statusBucketPillStyle } from "../lib/incidentStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  items: CombinedItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (item: CombinedItem) => void;
  // Claves "kind:id" -- ver IncidentesPage.tsx.
  selectedKey: string | null;
  flashKey: string | null;
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

export default function IncidentesTable({ items, loading, hasFilters, onSelect, selectedKey, flashKey }: Props) {
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
            <th className="pb-2 pr-3 font-semibold">Risk score</th>
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
                    <div className="flex items-center gap-2.5 justify-end">
                      <button
                        disabled
                        title="ALFA-Sentinel no puede aislar un host todavía: el agente no tiene forma de recibir ni ejecutar un comando remoto."
                        className="flex items-center gap-1.5 text-[11.5px] font-bold px-2 py-1 rounded cursor-not-allowed opacity-50 whitespace-nowrap transition-premium"
                        style={{ border: "1px solid var(--crit)", color: "var(--crit)", background: "var(--crit-soft)" }}
                      >
                        <i className="ph-fill ph-plugs text-[13px]" />
                        Aislar equipo
                      </button>
                      <button
                        onClick={() => onSelect(item)}
                        className="flex items-center gap-1.5 text-[11.5px] font-bold border-0 bg-transparent cursor-pointer whitespace-nowrap transition-premium btn-hover"
                        style={{ color: "var(--brand)" }}
                      >
                        Ver más detalles
                        <i className="ph-fill ph-arrow-right text-[13px]" />
                      </button>
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
