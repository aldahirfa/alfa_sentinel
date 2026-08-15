import type { CombinedItem } from "../types/incidentes";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { statusBucketPillStyle } from "../lib/incidentStatus";

interface Props {
  items: CombinedItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (item: CombinedItem) => void;
}

function rowAccent(item: CombinedItem): string | null {
  if (item.severity === "CRITICAL") return "var(--crit)";
  if (item.severity === "HIGH") return "var(--high)";
  if (item.severity === "SUSPICIOUS") return "var(--warn)";
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

export default function IncidentesTable({ items, loading, hasFilters, onSelect }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Código</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Regla</th>
            <th className="pb-2 pr-3 font-semibold">Severidad</th>
            <th className="pb-2 pr-3 font-semibold">Risk score</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Responsable</th>
            <th className="pb-2 pr-3 font-semibold">Fecha</th>
            <th className="pb-2 font-semibold" />
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
                  ? "Ningún incidente o alerta coincide con la búsqueda o los filtros aplicados."
                  : "Todavía no hay incidentes ni alertas registrados."}
              </td>
            </tr>
          ) : (
            items.map((item) => {
              const accent = rowAccent(item);
              return (
                <tr
                  key={`${item.kind}-${item.id}`}
                  className="border-t transition-colors"
                  style={{ borderColor: "var(--line-soft)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                >
                  <td className="py-2.5 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <div className="flex items-center gap-1.5 pl-2">
                      <i
                        className={item.kind === "incident" ? "ph-fill ph-siren" : "ph ph-warning"}
                        style={{ fontSize: "12px", color: "var(--tx-mute)" }}
                      />
                      <span className="font-semibold" style={{ color: "var(--tx)" }}>{item.code}</span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>
                    <span className="truncate block max-w-[160px]">{item.rule_label}</span>
                  </td>
                  <td className="py-2.5 pr-3">
                    {item.severity ? (
                      <span
                        className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded"
                        style={severityPillStyle(item.severity)}
                      >
                        {SEVERITY_LABEL[item.severity].toUpperCase()}
                      </span>
                    ) : (
                      <span style={{ color: "var(--tx-mute)" }}>—</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 tabular-nums font-medium" style={{ color: "var(--tx)" }}>
                    {item.risk_score !== null ? item.risk_score.toFixed(1) : "—"}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="text-[10.5px] font-medium px-2 py-0.5 rounded w-fit inline-block"
                      style={statusBucketPillStyle(item.status_bucket)}
                    >
                      {item.status_label}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: item.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>
                    {item.assigned_to_name ?? "Sin asignar"}
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{item.created_at}</td>
                  <td className="py-2.5">
                    <button
                      onClick={() => onSelect(item)}
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
