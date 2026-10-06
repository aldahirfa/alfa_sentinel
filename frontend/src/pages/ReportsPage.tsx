import { useEffect, useRef, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import ReportsSummaryCards from "../components/ReportsSummaryCards";
import GenerateReportForm from "../components/GenerateReportForm";
import ReportsHistoryTable from "../components/ReportsHistoryTable";
import ReportsPagination from "../components/ReportsPagination";
import { fetchReportes } from "../api/client";
import type { ReportsResponse } from "../types/reports";
import { useLiveRefresh } from "../hooks/useLiveRefresh";

export default function ReportsPage({ active }: { active: boolean }) {
  const [page, setPage] = useState(1);
  const liveTick = useLiveRefresh(active);
  const requestSeq = useRef(0);
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // 'silent': recarga en segundo plano (useLiveRefresh), sin "cargando"
  // y sin reemplazar la tabla por un error si falla una vez. Solo se
  // aplica la respuesta del pedido más reciente.
  function load(silent = false) {
    const seq = ++requestSeq.current;
    if (!silent) setLoading(true);
    fetchReportes(page)
      .then((res) => {
        if (seq === requestSeq.current) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (seq === requestSeq.current && !silent) setError("No se pudo cargar el historial de informes.");
      })
      .finally(() => {
        if (seq === requestSeq.current) setLoading(false);
      });
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => {
    if (liveTick) load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveTick]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="reportes"
        eyebrow="Documentación y evidencia"
        title="Generación y consulta de informes"
        description="Consolida información de seguridad, endpoints e incidentes en documentos preparados para revisión y respaldo institucional."
      />

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
