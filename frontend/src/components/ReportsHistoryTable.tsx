import type { ReportHistoryItem } from "../types/reports";

interface Props {
  history: ReportHistoryItem[];
  loading: boolean;
}

function formatIcon(format: string) {
  return format === "PDF" ? "ph-fill ph-file-pdf" : "ph-fill ph-file-xls";
}

export default function ReportsHistoryTable({ history, loading }: Props) {
  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
          <i className="ph ph-archive" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Archivo documental</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Historial de informes</div>
        </div>
        {!loading && <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{history.length} en esta página</div>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[940px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Informe</th>
              <th className="px-3 py-3 font-semibold">Período</th>
              <th className="px-3 py-3 font-semibold">Alcance</th>
              <th className="px-3 py-3 font-semibold">Generado por</th>
              <th className="px-3 py-3 font-semibold">Fecha</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "62%" }} /></td>)}
                </tr>
              ))
            ) : history.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                    <i className="ph ph-files" style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>Sin informes generados</div>
                  <div className="text-[9.5px] mt-1">Los nuevos documentos aparecerán aquí después de su generación.</div>
                </td>
              </tr>
            ) : (
              history.map((r) => (
                <tr key={r.id} className="border-t transition-premium" style={{ borderColor: "var(--line-soft)" }} onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")} onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <td className="px-4 py-3.5 min-w-[260px]">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: r.format === "PDF" ? "var(--crit-soft)" : "var(--ok-soft)", color: r.format === "PDF" ? "var(--crit)" : "var(--ok)" }}>
                        <i className={formatIcon(r.format)} style={{ fontSize: "17px" }} />
                      </div>
                      <div className="min-w-0">
                        <div className="font-semibold truncate" style={{ color: "var(--tx)" }}>{r.report_type_label}</div>
                        <div className="mono-data text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{r.code} · {r.format}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3.5" style={{ color: "var(--tx-dim)" }}>{r.period_label}</td>
                  <td className="px-3 py-3.5"><span className="inline-flex px-2 py-1 rounded-lg text-[9.5px]" style={{ background: "var(--brand-fill)", color: "var(--tx-dim)", border: "1px solid var(--brand-soft)" }}>{r.endpoint}</span></td>
                  <td className="px-3 py-3.5" style={{ color: "var(--tx-dim)" }}>{r.generated_by}</td>
                  <td className="px-3 py-3.5 whitespace-nowrap tabular-nums" style={{ color: "var(--tx-mute)" }}>{r.created_at}</td>
                  <td className="px-4 py-3.5 text-right">
                    <a href={`/reportes/${r.id}/archivo`} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border no-underline whitespace-nowrap transition-premium btn-hover" style={{ color: "var(--brand)", background: "var(--brand-fill)", borderColor: "var(--brand-soft)" }}>
                      <i className="ph ph-download-simple" style={{ fontSize: "13px" }} />
                      <span className="text-[10px] font-semibold">Descargar</span>
                    </a>
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
