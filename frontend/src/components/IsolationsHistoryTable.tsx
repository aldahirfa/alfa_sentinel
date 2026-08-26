import { useState } from "react";
import type { IsolationRecord } from "../types/respuesta";
import { releaseIsolation } from "../api/client";
import { RELEASE_ICON_CLASS, SPINNER_ICON_CLASS, RELEASE_LABEL_COMPACT, SENDING_LABEL, RELEASE_TOOLTIP } from "../lib/isolationUi";

interface Props {
  items: IsolationRecord[];
  loading: boolean;
  onReleased: () => void;
}

export default function IsolationsHistoryTable({ items, loading, onReleased }: Props) {
  const [releasingId, setReleasingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  async function handleRelease(isolationId: number) {
    setReleasingId(isolationId);
    setRowError(null);
    try {
      await releaseIsolation(isolationId);
      onReleased();
    } catch (err) {
      setRowError({ id: isolationId, message: err instanceof Error ? err.message : "No se pudo enviar la orden de liberación." });
    } finally {
      setReleasingId(null);
    }
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-clock-counter-clockwise" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Trazabilidad de contención</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Historial de aislamientos</div>
        </div>
        {!loading && <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{items.length} registros</div>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[1320px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Tipo</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Solicitado</th>
              <th className="px-3 py-3 font-semibold">Solicitado por</th>
              <th className="px-3 py-3 font-semibold">Ejecutado</th>
              <th className="px-3 py-3 font-semibold">Resultado</th>
              <th className="px-3 py-3 font-semibold">Liberado</th>
              <th className="px-3 py-3 font-semibold">Incidente</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {Array.from({ length: 10 }).map((_, j) => <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "62%" }} /></td>)}
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                    <i className="ph ph-shield" style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>Sin aislamientos registrados</div>
                  <div className="text-[9.5px] mt-1">Las acciones de contención ejecutadas aparecerán aquí con su trazabilidad.</div>
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
                  <td className="px-4 py-3.5 font-semibold" style={{ color: "var(--tx)" }}>{item.hostname}</td>
                  <td className="px-3 py-3.5" style={{ color: "var(--tx-dim)" }}>{item.isolation_type_label}</td>
                  <td className="px-3 py-3.5"><span className="inline-flex px-2 py-1 rounded-md text-[9px] font-semibold" style={{ background: item.status === "EXECUTED" ? "var(--crit-soft)" : item.status === "RELEASE_REQUESTED" ? "var(--warn-soft)" : "var(--brand-fill)", color: item.status === "EXECUTED" ? "var(--crit)" : item.status === "RELEASE_REQUESTED" ? "var(--warn)" : "var(--tx-dim)" }}>{item.status_label}</span></td>
                  <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.requested_at}</td>
                  <td className="px-3 py-3.5" style={{ color: item.requested_by_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>{item.requested_by_name ?? "Automático (motor heurístico)"}</td>
                  <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.executed_at ?? "—"}</td>
                  <td className="px-3 py-3.5 max-w-[220px] truncate" style={{ color: "var(--tx-mute)" }} title={item.result ?? undefined}>{item.result ?? "—"}</td>
                  <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.released_at ?? "—"}</td>
                  <td className="px-3 py-3.5">
                    <a href={`/incidentes/${item.incident_id}`} className="inline-flex items-center gap-1.5 text-[10px] font-semibold no-underline whitespace-nowrap transition-premium btn-hover" style={{ color: "var(--brand)" }}>
                      Ver #{item.incident_id}<i className="ph ph-arrow-right" style={{ fontSize: "12px" }} />
                    </a>
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    {item.status === "EXECUTED" && (
                      <button
                        disabled={releasingId === item.id}
                        onClick={(e) => { e.stopPropagation(); handleRelease(item.id); }}
                        title={RELEASE_TOOLTIP}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border text-[10px] font-semibold whitespace-nowrap cursor-pointer disabled:opacity-50 transition-premium btn-hover"
                        style={{ color: "var(--warn)", background: "var(--warn-fill)", borderColor: "var(--warn-soft)" }}
                      >
                        <i className={releasingId === item.id ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} />
                        {releasingId === item.id ? SENDING_LABEL : RELEASE_LABEL_COMPACT}
                      </button>
                    )}
                    {item.status === "RELEASE_REQUESTED" && <span className="text-[10px] font-semibold whitespace-nowrap" style={{ color: "var(--warn)" }}><i className="ph-fill ph-hourglass-medium mr-1" />Liberando...</span>}
                    {rowError?.id === item.id && <div className="text-[9px] mt-1" style={{ color: "var(--crit)" }}>{rowError.message}</div>}
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
