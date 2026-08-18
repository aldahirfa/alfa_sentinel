import type { AlertListItem } from "../types/alerts";
import { severityPillStyle } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  alerts: AlertListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
  // Alerta cuyo drawer está abierto ahora mismo (indicador persistente
  // y sutil) y, mientras dure, la que además debe "flashear" (ver
  // hooks/useRowFlash.ts) -- misma alerta al principio, luego flashId
  // vuelve a null y solo queda el indicador persistente.
  selectedId: number | null;
  flashId: number | null;
}

function rowAccent(a: AlertListItem): string | null {
  if (a.severity === "CRÍTICO") return "var(--crit)";
  if (a.severity === "ALTO") return "var(--high)";
  if (a.severity === "MEDIO") return "var(--warn)";
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

export default function AlertsTable({ alerts, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  return (
    <section
      className="rounded-xl border p-5 overflow-x-auto shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-widest uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
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
              const isSelected = a.id === selectedId;
              const isFlashing = a.id === flashId;
              const selStyle = rowSelectionStyle(isSelected, isFlashing);
              return (
                <tr
                  key={a.id}
                  className="border-t transition-colors cursor-pointer group"
                  style={{ borderColor: "var(--line-soft)", ...selStyle }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = selStyle.background as string)}
                >
                  <td className="py-3 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <span
                      className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full"
                      style={severityPillStyle(a.severity)}
                    >
                      {a.severity.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 pr-3">
                    <div className="font-semibold tracking-tight" style={{ color: "var(--tx)" }}>{a.title}</div>
                    {/* Cantidad de señales, no el nombre de una regla
                        puntual -- mostrar una sola regla acá era
                        exactamente el problema reportado (2026-08-18,
                        ver PENDIENTES.md, "Corrección definitiva en la
                        lógica y presentación de ALERTAS"): con más de
                        una regla vinculada, esa regla se elegía de
                        forma arbitraria. El detalle las lista todas. */}
                    {a.rule_count > 0 && (
                      <div className="text-[11px] mt-0.5 font-medium" style={{ color: "var(--tx-mute)" }}>
                        {a.rule_count === 1 ? "1 señal" : `${a.rule_count} señales`}
                      </div>
                    )}
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{a.hostname}</td>
                  <td className="py-3 pr-3 tabular-nums font-bold" style={{ color: "var(--tx)" }}>
                    {a.risk_score.toFixed(1)}
                  </td>
                  <td className="py-3 pr-3">
                    <span
                      className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full w-fit inline-block"
                      style={{ ...statusPillStyle(a.status), border: `1px solid ${statusPillStyle(a.status).color}` }}
                    >
                      {a.status_label}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{a.created_at}</td>
                  <td className="py-3 pr-3">
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
                  <td className="py-3">
                    <button
                      onClick={() => onSelect(a.id)}
                      className="flex items-center gap-1.5 text-[11.5px] font-bold border-0 bg-transparent cursor-pointer whitespace-nowrap transition-premium btn-hover"
                      style={{ color: "var(--brand)" }}
                    >
                      Detalles
                      <i className="ph-fill ph-arrow-right text-[13px]" />
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
