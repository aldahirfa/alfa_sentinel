import type { IsolationRecord } from "../types/respuesta";

interface Props {
  items: IsolationRecord[];
  loading: boolean;
}

export default function IsolationsHistoryTable({ items, loading }: Props) {
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
            <th className="pb-2 pr-3 font-semibold">Solicitado por</th>
            <th className="pb-2 pr-3 font-semibold">Solicitado</th>
            <th className="pb-2 pr-3 font-semibold">Liberado</th>
            <th className="pb-2 font-semibold">Incidente</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 7 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-info text-xl block mb-2" />
                Todavía no hay ningún aislamiento registrado -- el motor heurístico recomienda aislar cuando
                se cumple la política de contención (honeyfile + actividad de archivos fuerte, o severidad
                crítica con múltiples indicadores), pero ejecutarlo de verdad sigue siendo manual: el agente
                no tiene forma de recibir ni ejecutar un comando remoto.
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
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.requested_by_name ?? "—"}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.requested_at}</td>
                <td className="py-3 pr-3 font-medium" style={{ color: "var(--tx-mute)" }}>{item.released_at ?? "—"}</td>
                <td className="py-3">
                  <a href={`/incidentes/${item.incident_id}`} className="flex items-center gap-1.5 text-[11.5px] font-bold no-underline whitespace-nowrap transition-premium btn-hover" style={{ color: "var(--brand)" }}>
                    Ver #{item.incident_id}
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
