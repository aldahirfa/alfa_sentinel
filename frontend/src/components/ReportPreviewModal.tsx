import { useEffect, useState, type ReactNode } from "react";
import type { ReportPreview, ReportSheet } from "../types/reports";

interface Props {
  // Mientras sea null la ventana está cerrada. Cambiarla vuelve a cargar.
  load: (() => Promise<ReportPreview>) | null;
  title: string;
  subtitle: string;
  onClose: () => void;
  // Botones del pie (p. ej. "Generar informe" o "Descargar").
  actions?: ReactNode;
}

function SheetView({ sheet }: { sheet: ReportSheet }) {
  const columns = Math.max(1, ...sheet.rows.map((r) => r.length));
  return (
    <div className="overflow-auto h-full">
      <table className="border-collapse text-[11px] min-w-full">
        <tbody>
          {sheet.rows.map((row, i) => (
            <tr key={i} className="border-b" style={{ borderColor: "var(--line-soft)" }}>
              <td className="px-2 py-1.5 text-right text-[9px] tabular-nums select-none" style={{ color: "var(--tx-mute)", background: "var(--surf2)" }}>{i + 1}</td>
              {row.length <= 1 ? (
                <td colSpan={columns} className="px-3 py-1.5 whitespace-nowrap font-semibold" style={{ color: "var(--tx)" }}>{row[0] ?? ""}</td>
              ) : (
                row.map((cell, j) => (
                  <td key={j} className="px-3 py-1.5 whitespace-nowrap border-l" style={{ borderColor: "var(--line-soft)", color: "var(--tx-dim)" }}>{cell}</td>
                ))
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {sheet.truncated && (
        <div className="px-3 py-2 text-[10px]" style={{ color: "var(--tx-mute)" }}>
          La vista previa muestra las primeras filas; el archivo completo tiene más.
        </div>
      )}
    </div>
  );
}

export default function ReportPreviewModal({ load, title, subtitle, onClose, actions }: Props) {
  const [preview, setPreview] = useState<ReportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sheetIndex, setSheetIndex] = useState(0);

  useEffect(() => {
    if (!load) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setPreview(null);
    setError(null);
    setSheetIndex(0);
    load()
      .then((result) => {
        if (result.kind === "pdf") objectUrl = result.url;
        if (cancelled) {
          if (objectUrl) URL.revokeObjectURL(objectUrl);
        } else {
          setPreview(result);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "No se pudo cargar la vista previa.");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [load]);

  useEffect(() => {
    if (!load) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [load, onClose]);

  if (!load) return null;

  const sheets = preview?.kind === "sheets" ? preview.sheets : [];

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-[50]" style={{ background: "rgba(0,0,0,0.45)" }} />
      <div className="fixed inset-0 z-[51] flex items-center justify-center p-4 pointer-events-none">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="pointer-events-auto w-full max-w-5xl h-[88vh] rounded-2xl border flex flex-col shadow-2xl overflow-hidden"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4" style={{ borderColor: "var(--line-soft)" }}>
            <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <i className="ph ph-eye" style={{ fontSize: "17px" }} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Vista previa</div>
              <div className="text-[14px] font-semibold mt-0.5 truncate" style={{ color: "var(--tx)" }}>{title}</div>
              <div className="text-[10px] mt-0.5 truncate" style={{ color: "var(--tx-mute)" }}>{subtitle}</div>
            </div>
            <button onClick={onClose} className="w-8 h-8 rounded-lg grid place-items-center border-0 cursor-pointer transition-premium btn-hover" style={{ background: "var(--surf2)", color: "var(--tx-mute)" }} title="Cerrar (Esc)">
              <i className="ph ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>

          {sheets.length > 1 && (
            <div className="px-5 pt-3 flex gap-1.5 border-b" style={{ borderColor: "var(--line-soft)" }}>
              {sheets.map((s, i) => (
                <button key={s.name} onClick={() => setSheetIndex(i)} className="px-3 py-1.5 rounded-t-lg text-[10.5px] font-semibold border-0 cursor-pointer" style={i === sheetIndex ? { background: "var(--brand-soft)", color: "var(--brand)" } : { background: "transparent", color: "var(--tx-mute)" }}>
                  {s.name}
                </button>
              ))}
            </div>
          )}

          <div className="flex-1 min-h-0" style={{ background: "var(--surf2)" }}>
            {error ? (
              <div className="h-full grid place-items-center text-center px-6" style={{ color: "var(--crit)" }}>
                <div>
                  <i className="ph ph-warning-circle" style={{ fontSize: "26px" }} />
                  <div className="text-[12px] font-semibold mt-2">No se pudo cargar la vista previa</div>
                  <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
                </div>
              </div>
            ) : !preview ? (
              <div className="h-full grid place-items-center" style={{ color: "var(--tx-mute)" }}>
                <div className="flex items-center gap-2 text-[11px]"><i className="ph ph-spinner animate-spin" /> Preparando la vista previa...</div>
              </div>
            ) : preview.kind === "pdf" ? (
              <iframe src={preview.url} title={title} className="w-full h-full border-0" />
            ) : sheets.length === 0 ? (
              <div className="h-full grid place-items-center text-[11px]" style={{ color: "var(--tx-mute)" }}>El informe no tiene hojas.</div>
            ) : (
              <div className="h-full" style={{ background: "var(--surf)" }}><SheetView sheet={sheets[Math.min(sheetIndex, sheets.length - 1)]} /></div>
            )}
          </div>

          {actions && (
            <div className="px-5 py-3 border-t flex items-center justify-end gap-2" style={{ borderColor: "var(--line-soft)" }}>
              {actions}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
