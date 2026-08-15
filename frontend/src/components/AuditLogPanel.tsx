import type { AuditLogEntry } from "../types/admin";

interface Props {
  entries: AuditLogEntry[];
  loading: boolean;
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function AuditLogPanel({ entries, loading, page, totalPages, total, onPageChange }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Registro de actividad</h3>
        <span className="text-[11px]" style={{ color: "var(--tx-mute)" }}>{total} registros</span>
      </div>

      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Acción</th>
            <th className="pb-2 pr-3 font-semibold">Usuario</th>
            <th className="pb-2 pr-3 font-semibold">Detalle</th>
            <th className="pb-2 font-semibold">Fecha</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 4 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : entries.length === 0 ? (
            <tr>
              <td colSpan={4} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-scroll text-xl block mb-2" />
                Todavía no hay actividad registrada.
              </td>
            </tr>
          ) : (
            entries.map((e, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                <td className="py-2.5 pr-3 font-medium" style={{ color: "var(--tx)" }}>{e.action_label}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{e.user_name}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{e.description ?? "—"}</td>
                <td className="py-2.5" style={{ color: "var(--tx-mute)" }}>{e.created_at}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-1.5 mt-3">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="w-[30px] h-[30px] rounded-lg border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
          >
            <i className="ph ph-caret-left text-xs" />
          </button>
          <span className="text-[11.5px] px-2" style={{ color: "var(--tx-dim)" }}>Página {page} de {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="w-[30px] h-[30px] rounded-lg border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
          >
            <i className="ph ph-caret-right text-xs" />
          </button>
        </div>
      )}
    </section>
  );
}
