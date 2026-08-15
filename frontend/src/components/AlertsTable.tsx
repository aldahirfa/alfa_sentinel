import type { AlertListItem } from "../types/alerts";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";

interface Props {
  alerts: AlertListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
}

function rowAccent(a: AlertListItem): string | null {
  if (a.severity === "CRITICAL") return "var(--crit)";
  if (a.severity === "HIGH") return "var(--high)";
  if (a.severity === "SUSPICIOUS") return "var(--warn)";
  return null;
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
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

export default function AlertsTable({ alerts, loading, hasFilters, onSelect }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Severidad</th>
            <th className="pb-2 pr-3 font-semibold">Alerta</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Risk score</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Fecha</th>
            <th className="pb-2 pr-3 font-semibold">Incidente</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
          ) : alerts.length === 0 ? (
            <tr>
              <td colSpan={8} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-magnifying-glass text-xl block mb-2" />
                {hasFilters
                  ? "Ninguna alerta coincide con la búsqueda o los filtros aplicados."
                  : "Todavía no hay alertas registradas."}
              </td>
            </tr>
          ) : (
            alerts.map((a) => {
              const accent = rowAccent(a);
              return (
                <tr
                  key={a.id}
                  className="border-t transition-colors"
                  style={{ borderColor: "var(--line-soft)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                >
                  <td className="py-2.5 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <span
                      className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded pl-2"
                      style={severityPillStyle(a.severity)}
                    >
                      {SEVERITY_LABEL[a.severity].toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <div className="font-semibold" style={{ color: "var(--tx)" }}>{a.title}</div>
                    {a.rule_name && (
                      <div className="text-[11px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{a.rule_name}</div>
                    )}
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{a.hostname}</td>
                  <td className="py-2.5 pr-3 tabular-nums font-medium" style={{ color: "var(--tx)" }}>
                    {a.risk_score.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="text-[10.5px] font-medium px-2 py-0.5 rounded w-fit inline-block"
                      style={statusPillStyle(a.status)}
                    >
                      {a.status_label}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{a.created_at}</td>
                  <td className="py-2.5 pr-3">
                    {a.incident_id ? (
                      <a
                        href={`/incidentes/${a.incident_id}`}
                        className="text-[11.5px] font-medium no-underline"
                        style={{ color: "var(--brand)" }}
                      >
                        #{a.incident_id}
                      </a>
                    ) : (
                      <span style={{ color: "var(--tx-mute)" }}>—</span>
                    )}
                  </td>
                  <td className="py-2.5">
                    <button
                      onClick={() => onSelect(a.id)}
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
