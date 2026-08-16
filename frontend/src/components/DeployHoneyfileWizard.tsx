import { useState, useEffect } from "react";
import { deployHoneyfile } from "../api/client";
import type { AvailableAgent } from "../types/honeyfiles";

interface Props {
  open: boolean;
  availableAgents: AvailableAgent[];
  onClose: () => void;
  onDeployed: (message: string) => void;
}

const FILE_TYPE_OPTIONS = [
  { value: "xlsx", label: "Documento Excel (.xlsx)" },
  { value: "docx", label: "Documento Word (.docx)" },
  { value: "zip", label: "Archivo ZIP (.zip)" },
  { value: "txt", label: "Texto plano (.txt)" },
  { value: "pdf", label: "Documento PDF (.pdf)" },
];

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line-soft)",
  color: "var(--tx)",
};

export default function DeployHoneyfileWizard({ open, availableAgents, onClose, onDeployed }: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  const [fileName, setFileName] = useState("");
  const [fileType, setFileType] = useState("xlsx");
  const [targetPath, setTargetPath] = useState("%USERPROFILE%\\Desktop\\");
  const [platform, setPlatform] = useState<"windows" | "linux" | "all">("windows");
  const [content, setContent] = useState("");
  const [autoDeploy, setAutoDeploy] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<Set<number>>(() => new Set(availableAgents.map((a) => a.id)));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    if (open) {
      setRender(true);
      const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
      return () => cancelAnimationFrame(raf);
    } else if (render) {
      setEntered(false);
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
  }, [open, render]);

  if (!render) return null;

  function reset() {
    setStep(1);
    setFileName("");
    setFileType("xlsx");
    setTargetPath("%USERPROFILE%\\Desktop\\");
    setPlatform("windows");
    setContent("");
    setAutoDeploy(false);
    setSelectedAgents(new Set(availableAgents.map((a) => a.id)));
    setError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  function goStep2() {
    if (!fileName.trim()) {
      setError("Falta el nombre del archivo.");
      return;
    }
    if (!targetPath.trim()) {
      setError("Falta la ruta de destino en el cliente.");
      return;
    }
    setError(null);
    setStep(2);
  }

  function toggleAgent(id: number) {
    setSelectedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelectedAgents(checked ? new Set(availableAgents.map((a) => a.id)) : new Set());
  }

  async function handleDeploy() {
    if (!autoDeploy && selectedAgents.size === 0) {
      setError("Selecciona al menos un endpoint destino, o marca despliegue automático.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await deployHoneyfile({
        file_name: fileName.trim(),
        file_type: fileType,
        target_path: targetPath.trim(),
        platform,
        auto_deploy: autoDeploy,
        content: content.trim(),
        agent_ids: Array.from(selectedAgents),
      });
      onDeployed(result.message);
      handleClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo desplegar el honeyfile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div 
        onClick={handleClose} 
        className="fixed inset-0 z-40" 
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }} 
      />
      <div 
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{
          opacity: entered ? 1 : 0,
          transform: entered ? "scale(1)" : "scale(0.95)",
          transition: "opacity 200ms ease, transform 200ms ease",
        }}
      >
        <div
          className="w-full max-w-lg rounded-2xl border flex flex-col max-h-[88vh] shadow-2xl"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4" style={{ borderColor: "var(--line-soft)" }}>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
                Configuración de trampa
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
                Desplegar honeyfile
              </div>
            </div>
            <button
              onClick={handleClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph-fill ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>

          {/* Stepper */}
          <div className="px-5 pt-3 flex items-center gap-2 text-[12px]" style={{ color: "var(--tx-mute)" }}>
            <span className="flex items-center gap-1.5" style={{ color: step === 1 ? "var(--brand)" : "var(--tx-mute)" }}>
              <span className="w-5 h-5 rounded-full grid place-items-center text-[10px] font-semibold" style={{ background: step === 1 ? "var(--brand)" : "var(--surf3)", color: step === 1 ? "#fff" : "var(--tx-mute)" }}>1</span>
              Parámetros de trampa
            </span>
            <i className="ph ph-arrow-right text-[11px]" />
            <span className="flex items-center gap-1.5" style={{ color: step === 2 ? "var(--brand)" : "var(--tx-mute)" }}>
              <span className="w-5 h-5 rounded-full grid place-items-center text-[10px] font-semibold" style={{ background: step === 2 ? "var(--brand)" : "var(--surf3)", color: step === 2 ? "#fff" : "var(--tx-mute)" }}>2</span>
              Agentes destino
            </span>
          </div>

          <div className="px-5 py-4 overflow-y-auto flex-1">
            {error && (
              <div className="mb-3 rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                {error}
              </div>
            )}

            {step === 1 ? (
              <div className="flex flex-col gap-3.5">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Nombre del archivo</label>
                    <input
                      type="text"
                      value={fileName}
                      onChange={(e) => setFileName(e.target.value)}
                      placeholder="Ej: Documento_Confidencial"
                      className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
                      style={fieldStyle}
                    />
                  </div>
                  <div>
                    <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Tipo / extensión</label>
                    <select
                      value={fileType}
                      onChange={(e) => setFileType(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg text-[13px] outline-none cursor-pointer transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
                      style={fieldStyle}
                    >
                      {FILE_TYPE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Ruta de destino en el cliente</label>
                  <input
                    type="text"
                    value={targetPath}
                    onChange={(e) => setTargetPath(e.target.value)}
                    placeholder="Ej: C:\Users\Public\Docs\ o /var/backups/"
                    className="w-full px-3 py-2 rounded-lg text-[12.5px] outline-none font-mono font-medium transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                    style={fieldStyle}
                  />
                </div>

                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Plataforma objetivo</label>
                  <div className="flex gap-4 text-[13px]" style={{ color: "var(--tx)" }}>
                    {([["windows", "Windows", "ph-windows-logo"], ["linux", "Linux / Ubuntu", "ph-linux-logo"], ["all", "Todas las plataformas", "ph-circles-four"]] as const).map(([val, label, icon]) => (
                      <label key={val} className="flex items-center gap-1.5 cursor-pointer font-medium hover:text-[var(--tx)] transition-colors" style={{ color: platform === val ? "var(--brand)" : "var(--tx-mute)" }}>
                        <input type="radio" name="platform" checked={platform === val} onChange={() => setPlatform(val as any)} />
                        <i className={`ph ${icon} text-[15px]`} />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
                    Contenido del archivo (texto plano, guardado con la extensión elegida)
                  </label>
                  <textarea
                    rows={3}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    placeholder="Documento confidencial. No modificar ni distribuir sin autorización."
                    className="w-full px-3 py-2 rounded-lg text-[12.5px] outline-none resize-y transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
                    style={fieldStyle}
                  />
                  <p className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
                    No se genera un .xlsx/.docx/.pdf real -- es texto plano guardado con esa extensión, suficiente para que el monitor de archivos y la detección de honeyfile reaccionen.
                  </p>
                </div>

                <label className="flex items-start gap-2 cursor-pointer text-[13px]" style={{ color: "var(--tx)" }}>
                  <input type="checkbox" checked={autoDeploy} onChange={(e) => setAutoDeploy(e.target.checked)} className="mt-0.5" />
                  <span>
                    <div className="flex items-center gap-1.5 font-semibold">
                      <i className="ph-fill ph-rocket-launch text-[15px]" style={{ color: "var(--brand)" }} />
                      Despliegue automático a futuros endpoints compatibles
                    </div>
                    <div className="text-[10.5px] mt-1 leading-relaxed font-medium" style={{ color: "var(--tx-mute)" }}>
                      Si activas esto, el Paso 2 es opcional. El honeyfile se distribuirá automáticamente en cuanto un agente de la plataforma objetivo empiece a reportar.
                    </div>
                  </span>
                </label>
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                <p className="text-[12px]" style={{ color: "var(--tx-mute)" }}>
                  Selecciona los endpoints donde el agente creará físicamente este señuelo:
                </p>
                <label className="flex items-center gap-2 text-[12.5px] font-semibold cursor-pointer" style={{ color: "var(--tx)" }}>
                  <input
                    type="checkbox"
                    checked={selectedAgents.size === availableAgents.length && availableAgents.length > 0}
                    onChange={(e) => toggleAll(e.target.checked)}
                  />
                  Seleccionar todos los equipos disponibles
                </label>
                <div className="flex flex-col gap-1.5 max-h-[280px] overflow-y-auto">
                  {availableAgents.length === 0 ? (
                    <p className="text-[12px] py-4 text-center" style={{ color: "var(--tx-mute)" }}>No hay endpoints registrados todavía.</p>
                  ) : (
                    availableAgents.map((a) => (
                      <label
                        key={a.id}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-premium hover:-translate-y-0.5 hover:shadow-sm"
                        style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}
                      >
                        <input type="checkbox" checked={selectedAgents.has(a.id)} onChange={() => toggleAgent(a.id)} className="w-3.5 h-3.5 rounded-sm" />
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>{a.hostname}</div>
                          <div className="text-[11px] font-medium mt-1 flex items-center gap-1" style={{ color: "var(--tx-mute)" }}>
                            <i className={a.operating_system.toLowerCase().includes("win") ? "ph ph-windows-logo" : a.operating_system.toLowerCase().includes("linux") ? "ph ph-linux-logo" : "ph ph-desktop"} />
                            {a.operating_system} · IP: {a.ip_address}
                          </div>
                        </div>
                        <span
                          className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full whitespace-nowrap flex items-center gap-1"
                          style={a.is_live ? { background: "var(--ok-soft)", color: "var(--ok)" } : { background: "transparent", color: "var(--tx-mute)", border: "1px solid var(--line)" }}
                        >
                          {a.is_live && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--ok)" }} />}
                          {a.is_live ? "En línea" : "Desconectado"}
                        </span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="px-5 py-3.5 border-t flex items-center justify-between" style={{ borderColor: "var(--line-soft)" }}>
            {step === 2 ? (
              <button
                onClick={() => setStep(1)}
                className="px-4 py-2 rounded-lg text-[13px] font-bold cursor-pointer transition-premium btn-hover shadow-sm"
                style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
              >
                Atrás
              </button>
            ) : <span />}
            {step === 1 ? (
              <button
                onClick={goStep2}
                className="px-5 py-2 rounded-lg text-[13px] font-bold cursor-pointer border-0 transition-premium btn-hover shadow-sm"
                style={{ background: "var(--brand)", color: "#fff" }}
              >
                Continuar
              </button>
            ) : (
              <button
                onClick={handleDeploy}
                disabled={saving}
                className="px-5 py-2 rounded-lg text-[13px] font-bold cursor-pointer border-0 disabled:opacity-50 transition-premium btn-hover shadow-sm"
                style={{ background: "var(--brand)", color: "#fff" }}
              >
                {saving ? "Desplegando..." : "Desplegar honeyfile"}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
