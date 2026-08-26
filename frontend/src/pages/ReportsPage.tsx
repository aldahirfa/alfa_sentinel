import { useEffect, useState } from "react";
import ReportsSummaryCards from "../components/ReportsSummaryCards";
import GenerateReportForm from "../components/GenerateReportForm";
import ReportsHistoryTable from "../components/ReportsHistoryTable";
import ReportsPagination from "../components/ReportsPagination";
import { fetchReportes } from "../api/client";
import type { ReportsResponse } from "../types/reports";

export default function ReportsPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  function load() {
    let cancelled = false;
    setLoading(true);
    fetchReportes(page)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar el historial de informes.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }

  useEffect(() => {
    return load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <main className="soc-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      {toast && (
        <div className="soc-panel rounded-2xl px-4 py-3 flex items-start gap-3" style={{ background: "var(--ok-soft)", borderColor: "color-mix(in srgb, var(--ok) 28%, var(--line-soft))" }}>
          <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
            <i className="ph-fill ph-check-circle" style={{ fontSize: "16px" }} />
          </div>
          <div>
            <div className="text-[10.5px] font-semibold" style={{ color: "var(--ok)" }}>Informe generado correctamente</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--tx-dim)" }}>{toast}</div>
          </div>
        </div>
      )}

      {data && <ReportsSummaryCards totalReports={data.total_reports} lastGeneratedAt={data.last_generated_at} lastGeneratedBy={data.last_generated_by} />}

      <div className="px-1 pt-1">
        <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Documentación y evidencia</div>
        <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>Generación y consulta de informes</div>
        <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
          Consolida información de seguridad, endpoints e incidentes en documentos preparados para revisión y respaldo institucional.
        </div>
      </div>

      {data && (
        <GenerateReportForm
          reportTypeOptions={data.report_type_options}
          periodOptions={data.period_options}
          endpointOptions={data.endpoint_options}
          onGenerated={(result) => {
            setToast(`${result.report.title} generado correctamente.`);
            setPage(1);
            load();
          }}
        />
      )}

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el archivo documental</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <>
          <ReportsHistoryTable history={data?.history ?? []} loading={loading} />
          {data && <ReportsPagination page={data.page} totalPages={data.total_pages} onPageChange={setPage} />}
        </>
      )}
    </main>
  );
}
