import { useState } from "react";
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
  border: "1px solid var(--line)",
  color: "var(--tx)",
};

export default function GenerateReportForm({ reportTypeOptions, periodOptions, endpointOptions, onGenerated }: Props) {
  const [reportType, setReportType] = useState<ReportType>("SECURITY");
  const [period, setPeriod] = useState<ReportPeriod>("30d");
  const [format, setFormat] = useState<ReportFormat>("PDF");
  const [endpointId, setEndpointId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <section
      className="rounded-[10px] border p-4 flex flex-col gap-3.5"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Generar nuevo informe</h3>

      {error && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Tipo de informe</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value as ReportType)}
            className="w-full px-2.5 py-2 rounded-[8px] text-[12.5px] outline-none cursor-pointer"
            style={fieldStyle}
          >
            {reportTypeOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Período</label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as ReportPeriod)}
            className="w-full px-2.5 py-2 rounded-[8px] text-[12.5px] outline-none cursor-pointer"
            style={fieldStyle}
          >
            {periodOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Endpoint</label>
          <select
            value={endpointId}
            onChange={(e) => setEndpointId(e.target.value)}
            className="w-full px-2.5 py-2 rounded-[8px] text-[12.5px] outline-none cursor-pointer"
            style={fieldStyle}
          >
            <option value="">Todos los endpoints</option>
            {endpointOptions.map((o) => (
              <option key={o.id} value={o.id}>{o.hostname}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Formato</label>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {(["PDF", "XLSX"] as ReportFormat[]).map((f) => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className="flex-1 px-2.5 py-1.5 rounded-md text-[12px] font-semibold border-0 cursor-pointer"
                style={format === f ? { background: "var(--brand)", color: "#fff" } : { background: "transparent", color: "var(--tx-mute)" }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={handleGenerate}
        disabled={saving}
        className="self-start flex items-center gap-2 px-4 py-2 rounded-[9px] text-[12.5px] font-semibold border-0 cursor-pointer disabled:opacity-50"
        style={{ background: "var(--brand)", color: "#fff" }}
      >
        <i className={saving ? "ph ph-spinner" : "ph ph-file-plus"} style={{ fontSize: "15px" }} />
        {saving ? "Generando..." : "Generar informe"}
      </button>
    </section>
  );
}
