import type { IsolationRecord } from "../types/respuesta";

interface Props {
  items: IsolationRecord[];
  loading: boolean;
}

export default function IsolationsHistoryTable({ items, loading }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold mb-3" style={{ color: "var(--tx)" }}>
        Historial de aislamientos
      </h3>
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
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
                Todavía no hay ningún aislamiento registrado -- el mecanismo existe en el diseño de la base
                de datos, pero ningún endpoint escribe ahí porque el agente no tiene forma de recibir ni
                ejecutar un comando remoto.
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{item.hostname}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{item.isolation_type}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{item.status}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{item.requested_by_name ?? "—"}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{item.requested_at}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{item.released_at ?? "—"}</td>
                <td className="py-2.5">
                  <a href={`/incidentes/${item.incident_id}`} className="text-[11.5px] font-medium no-underline" style={{ color: "var(--brand)" }}>
                    #{item.incident_id}
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
