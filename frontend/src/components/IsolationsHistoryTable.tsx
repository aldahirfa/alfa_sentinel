import { useState } from "react";
import type { IsolationRecord } from "../types/respuesta";
import { releaseIsolation } from "../api/client";
import { RELEASE_ICON_CLASS, SPINNER_ICON_CLASS, RELEASE_LABEL_COMPACT, SENDING_LABEL, RELEASE_TOOLTIP } from "../lib/isolationUi";

interface Props {
  items: IsolationRecord[];
  loading: boolean;
  // Refresca /api/respuesta después de liberar (2026-08-17, ver
  // PENDIENTES.md, "Aislamiento de host -- modo development,
  // laboratorio y producción") -- mismo criterio que el aislamiento
  // manual: el estado real vive en el servidor.
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
    <section
      className="rounded-xl border p-5 overflow-x-auto shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <h3 className="text-[14px] font-bold mb-4 tracking-tight" style={{ color: "var(--tx)" }}>
        Historial de aislamientos
      </h3>
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-widest uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Tipo</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Solicitado</th>
            <th className="pb-2 pr-3 font-semibold">Solicitado por</th>
            <th className="pb-2 pr-3 font-semibold">Ejecutado</th>
            <th className="pb-2 pr-3 font-semibold">Resultado</th>
            <th className="pb-2 pr-3 font-semibold">Liberado</th>
            <th className="pb-2 pr-3 font-semibold">Incidente</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 10 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={10} className="text-center py-8" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-info text-xl block mb-2" />
                Todavía no hay ningún aislamiento registrado -- el motor heurístico ordena aislar
                automáticamente cuando se cumple la política de contención (honeyfile + actividad de
                archivos fuerte, o severidad crítica con múltiples indicadores), el agente del endpoint
                lo ejecuta de verdad y confirma el resultado acá, y también se puede disparar manualmente
                desde los incidentes críticos de arriba.
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
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.isolation_type_label}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-dim)" }}>{item.status_label}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.requested_at}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: item.requested_by_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>
                  {item.requested_by_name ?? "Automático (motor heurístico)"}
                </td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.executed_at ?? "—"}</td>
                <td className="py-3 pr-3 font-medium max-w-[220px] truncate" style={{ color: "var(--tx-mute)" }} title={item.result ?? undefined}>{item.result ?? "—"}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.released_at ?? "—"}</td>
                <td className="py-3 pr-3">
                  <a href={`/incidentes/${item.incident_id}`} className="flex items-center gap-1.5 text-[11.5px] font-bold no-underline whitespace-nowrap transition-premium btn-hover" style={{ color: "var(--brand)" }}>
                    Ver #{item.incident_id}
                    <i className="ph-fill ph-arrow-right text-[13px]" />
                  </a>
                </td>
                <td className="py-3">
                  {item.status === "EXECUTED" && (
                    // Amarillo, nunca rojo (sección 11 de "ALFA_SENTINEL —
                    // CORRECCIÓN DE TIEMPO REAL...", 2026-08-17, ver
                    // PENDIENTES.md): rojo queda reservado para acciones de
                    // alto riesgo/destructivas (Aislar) -- Liberar es lo
                    // opuesto, restaurar conectividad, así que usa --warn.
                    <button
                      disabled={releasingId === item.id}
                      onClick={(e) => { e.stopPropagation(); handleRelease(item.id); }}
                      title={RELEASE_TOOLTIP}
                      className="flex items-center gap-1.5 text-[11.5px] font-bold whitespace-nowrap cursor-pointer border-0 bg-transparent disabled:opacity-50 transition-premium btn-hover"
                      style={{ color: "var(--warn)" }}
                    >
                      <i className={releasingId === item.id ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} />
                      {releasingId === item.id ? SENDING_LABEL : RELEASE_LABEL_COMPACT}
                    </button>
                  )}
                  {item.status === "RELEASE_REQUESTED" && (
                    <span className="text-[11px] font-bold whitespace-nowrap" style={{ color: "var(--warn)" }}>
                      <i className="ph-fill ph-hourglass-medium mr-1" />
                      Liberando...
                    </span>
                  )}
                  {rowError?.id === item.id && (
                    <div className="text-[10px] mt-1" style={{ color: "var(--crit)" }}>{rowError.message}</div>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
