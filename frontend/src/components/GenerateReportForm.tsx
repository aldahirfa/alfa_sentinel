import { useMemo, useState } from "react";
import { generateReport } from "../api/client";
import type { EndpointOption, GenerateReportResult, ReportFormat, ReportOption, ReportPeriod, ReportType } from "../types/reports";

interface Props {
  reportTypeOptions: ReportOption[];
  periodOptions: ReportOption[];
  endpointOptions: EndpointOption[];
  onGenerated: (result: GenerateReportResult) => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line-soft)",
  color: "var(--tx)",
};

export default function GenerateReportForm({ reportTypeOptions, periodOptions, endpointOptions, onGenerated }: Props) {
  const [reportType, setReportType] = useState<ReportType>("SECURITY");
  const [period, setPeriod] = useState<ReportPeriod>("30d");
  const [format, setFormat] = useState<ReportFormat>("PDF");
  const [endpointId, setEndpointId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reportLabel = useMemo(() => reportTypeOptions.find((o) => o.value === reportType)?.label ?? "Informe de seguridad", [reportTypeOptions, reportType]);
  const periodLabel = useMemo(() => periodOptions.find((o) => o.value === period)?.label ?? period, [periodOptions, period]);
  const endpointLabel = useMemo(() => endpointOptions.find((o) => String(o.id) === endpointId)?.hostname ?? "Todos los endpoints", [endpointOptions, endpointId]);

  async function handleGenerate() {
    setSaving(true);
    setError(null);
    try {
      const result = await generateReport({
        report_type: reportType,
        period,
        format,
        endpoint_id: endpointId ? Number(endpointId) : null,
      });
      onGenerated(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar el informe.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-file-plus" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Nuevo documento</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Generar informe institucional</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-0">
        <div className="p-5 xl:border-r" style={{ borderColor: "var(--line-soft)" }}>
          {error && (
            <div className="rounded-xl px-3.5 py-3 text-[11px] mb-4 flex items-start gap-2.5" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
              <i className="ph ph-warning-circle mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] font-semibold block mb-2" style={{ color: "var(--tx-mute)" }}>Tipo de informe</label>
              <select value={reportType} onChange={(e) => setReportType(e.target.value as ReportType)} className="w-full px-3 py-2.5 rounded-xl text-[12px] outline-none cursor-pointer transition-premium" style={fieldStyle}>
                {reportTypeOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-[10px] font-semibold block mb-2" style={{ color: "var(--tx-mute)" }}>Período analizado</label>
              <select value={period} onChange={(e) => setPeriod(e.target.value as ReportPeriod)} className="w-full px-3 py-2.5 rounded-xl text-[12px] outline-none cursor-pointer transition-premium" style={fieldStyle}>
                {periodOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-[10px] font-semibold block mb-2" style={{ color: "var(--tx-mute)" }}>Alcance de endpoints</label>
              <select value={endpointId} onChange={(e) => setEndpointId(e.target.value)} className="w-full px-3 py-2.5 rounded-xl text-[12px] outline-none cursor-pointer transition-premium" style={fieldStyle}>
                <option value="">Todos los endpoints</option>
                {endpointOptions.map((o) => <option key={o.id} value={o.id}>{o.hostname}</option>)}
              </select>
            </div>

            <div>
              <label className="text-[10px] font-semibold block mb-2" style={{ color: "var(--tx-mute)" }}>Formato de salida</label>
              <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                {(["PDF", "XLSX"] as ReportFormat[]).map((f) => (
                  <button key={f} type="button" onClick={() => setFormat(f)} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-[11px] font-semibold border-0 cursor-pointer transition-premium" style={format === f ? { background: "var(--brand)", color: "#fff", boxShadow: "var(--shadow)" } : { background: "transparent", color: "var(--tx-mute)" }}>
                    <i className={f === "PDF" ? "ph ph-file-pdf" : "ph ph-file-xls"} />
                    {f}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t flex items-center justify-between gap-4 flex-wrap" style={{ borderColor: "var(--line-soft)" }}>
            <div className="text-[9.5px] leading-relaxed max-w-[520px]" style={{ color: "var(--tx-mute)" }}>
              El informe se genera con la información registrada por el Sistema ALFA-Sentinel para el período y alcance seleccionados.
            </div>
            <button onClick={handleGenerate} disabled={saving} className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[11px] font-bold border-0 cursor-pointer disabled:opacity-50 transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff", boxShadow: "0 8px 24px var(--brand-glow)" }}>
              <i className={saving ? "ph ph-spinner" : "ph ph-file-arrow-down"} style={{ fontSize: "14px" }} />
              {saving ? "Generando informe..." : "Generar informe"}
            </button>
          </div>
        </div>

        <div className="p-5" style={{ background: "color-mix(in srgb, var(--surf2) 72%, transparent)" }}>
          <div className="text-[9px] font-bold tracking-[.14em] uppercase" style={{ color: "var(--tx-mute)" }}>Vista previa</div>
          <div className="mt-3 rounded-2xl border overflow-hidden" style={{ background: "var(--surf)", borderColor: "var(--line-soft)", boxShadow: "var(--shadow)" }}>
            <div className="h-1" style={{ background: "linear-gradient(90deg, var(--brand), var(--info))" }} />
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[8.5px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--brand)" }}>Sistema ALFA-Sentinel</div>
                  <div className="text-[14px] font-bold mt-1 leading-tight" style={{ color: "var(--tx)" }}>{reportLabel}</div>
                </div>
                <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                  <i className="ph ph-shield-check" style={{ fontSize: "17px" }} />
                </div>
              </div>

              <div className="mt-5 flex flex-col gap-2.5">
                <div className="flex justify-between gap-3 text-[9.5px]"><span style={{ color: "var(--tx-mute)" }}>Período</span><b style={{ color: "var(--tx-dim)" }}>{periodLabel}</b></div>
                <div className="flex justify-between gap-3 text-[9.5px]"><span style={{ color: "var(--tx-mute)" }}>Alcance</span><b className="truncate text-right" style={{ color: "var(--tx-dim)" }}>{endpointLabel}</b></div>
                <div className="flex justify-between gap-3 text-[9.5px]"><span style={{ color: "var(--tx-mute)" }}>Formato</span><b style={{ color: "var(--tx-dim)" }}>{format}</b></div>
              </div>

              <div className="mt-5 pt-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
                <div className="h-2 rounded-full w-[82%]" style={{ background: "var(--surf3)" }} />
                <div className="h-2 rounded-full w-full mt-2" style={{ background: "var(--surf3)" }} />
                <div className="h-2 rounded-full w-[68%] mt-2" style={{ background: "var(--surf3)" }} />
              </div>
            </div>
          </div>
          <div className="text-[9px] leading-relaxed mt-3" style={{ color: "var(--tx-mute)" }}>
            La vista previa representa la portada y metadatos del documento; el contenido final se construye con los datos reales del período.
          </div>
        </div>
      </div>
    </section>
  );
}
