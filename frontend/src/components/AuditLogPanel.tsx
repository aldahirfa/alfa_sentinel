import type { AuditLogEntry } from "../types/admin";

interface Props {
  entries: AuditLogEntry[];
  loading: boolean;
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
}

function actionIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes("usuario")) return "ph ph-user-circle";
  if (value.includes("token") || value.includes("agente")) return "ph ph-key";
  if (value.includes("config")) return "ph ph-sliders-horizontal";
  return "ph ph-activity";
}

export default function AuditLogPanel({ entries, loading, page, totalPages, total, onPageChange }: Props) {
  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-scroll" style={{ fontSize: "17px" }} /></div>
        <div><div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Trazabilidad administrativa</div><div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Registro de actividad</div></div>
        <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{total} registros</div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[820px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Acción</th>
              <th className="px-3 py-3 font-semibold">Usuario</th>
              <th className="px-3 py-3 font-semibold">Detalle</th>
              <th className="px-4 py-3 font-semibold">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "62%" }} /></td>)}</tr>)
            ) : entries.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-14" style={{ color: "var(--tx-mute)" }}><div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-scroll" style={{ fontSize: "22px" }} /></div><div className="font-semibold" style={{ color: "var(--tx-dim)" }}>Sin actividad registrada</div></td></tr>
            ) : (
              entries.map((e, i) => (
                <tr key={i} className="border-t transition-premium" style={{ borderColor: "var(--line-soft)" }} onMouseEnter={(ev) => (ev.currentTarget.style.background = "var(--surf2)")} onMouseLeave={(ev) => (ev.currentTarget.style.background = "transparent")}>
                  <td className="px-4 py-3.5 min-w-[210px]"><div className="flex items-center gap-3"><div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-fill)", color: "var(--brand)" }}><i className={actionIcon(e.action_label)} style={{ fontSize: "14px" }} /></div><div className="font-semibold" style={{ color: "var(--tx)" }}>{e.action_label}</div></div></td>
                  <td className="px-3 py-3.5"><span className="inline-flex px-2 py-1 rounded-lg text-[9.5px]" style={{ background: "var(--surf3)", color: "var(--tx-dim)" }}>{e.user_name}</span></td>
                  <td className="px-3 py-3.5 max-w-[440px]" style={{ color: "var(--tx-mute)" }}>{e.description ?? "—"}</td>
                  <td className="px-4 py-3.5 whitespace-nowrap tabular-nums" style={{ color: "var(--tx-mute)" }}>{e.created_at}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="px-4 py-3 border-t flex items-center justify-end gap-2" style={{ borderColor: "var(--line-soft)", background: "var(--surf2)" }}>
          <button disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="w-8 h-8 rounded-xl border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-premium btn-hover" style={{ borderColor: "var(--line-soft)", background: "var(--surf)", color: "var(--tx-dim)" }}><i className="ph ph-caret-left text-xs" /></button>
          <span className="text-[9.5px] px-2" style={{ color: "var(--tx-mute)" }}>Página <b style={{ color: "var(--tx-dim)" }}>{page}</b> de {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} className="w-8 h-8 rounded-xl border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-premium btn-hover" style={{ borderColor: "var(--line-soft)", background: "var(--surf)", color: "var(--tx-dim)" }}><i className="ph ph-caret-right text-xs" /></button>
        </div>
      )}
    </section>
  );
}
