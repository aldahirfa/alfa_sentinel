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
    return () => {
      cancelled = true;
    };
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
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {toast && (
        <div
          className="rounded-[10px] border px-4 py-3 text-[12.5px] flex items-start gap-2"
          style={{ background: "var(--ok-soft)", borderColor: "var(--ok)", color: "var(--ok)" }}
        >
          <i className="ph-fill ph-check-circle" style={{ fontSize: "16px", marginTop: "1px" }} />
          {toast}
        </div>
      )}

      {data && (
        <ReportsSummaryCards
          totalReports={data.total_reports}
          lastGeneratedAt={data.last_generated_at}
          lastGeneratedBy={data.last_generated_by}
        />
      )}

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
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
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
