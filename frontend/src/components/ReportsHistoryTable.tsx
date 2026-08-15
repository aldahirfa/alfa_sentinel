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
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold mb-3" style={{ color: "var(--tx)" }}>Historial de informes</h3>
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Informe</th>
            <th className="pb-2 pr-3 font-semibold">Período</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint</th>
            <th className="pb-2 pr-3 font-semibold">Generado por</th>
            <th className="pb-2 pr-3 font-semibold">Fecha</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 6 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : history.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-chart-bar text-xl block mb-2" />
                Todavía no se generó ningún informe. Usá el formulario de arriba para crear el primero.
              </td>
            </tr>
          ) : (
            history.map((r) => (
              <tr
                key={r.id}
                className="border-t transition-colors"
                style={{ borderColor: "var(--line-soft)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "")}
              >
                <td className="py-2.5 pr-3">
                  <div className="flex items-center gap-2 pl-2">
                    <i className={formatIcon(r.format)} style={{ fontSize: "15px", color: "var(--tx-mute)" }} />
                    <div className="min-w-0">
                      <div className="font-semibold" style={{ color: "var(--tx)" }}>{r.report_type_label}</div>
                      <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{r.code}</div>
                    </div>
                  </div>
                </td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{r.period_label}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{r.endpoint}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{r.generated_by}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{r.created_at}</td>
                <td className="py-2.5">
                  <a
                    href={`/reportes/${r.id}/archivo`}
                    className="flex items-center gap-1 text-[11.5px] font-medium no-underline whitespace-nowrap"
                    style={{ color: "var(--brand)" }}
                  >
                    <i className="ph ph-download-simple text-[13px]" />
                    Descargar
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
