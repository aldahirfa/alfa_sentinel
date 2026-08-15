import { useEffect, useState } from "react";
import { fetchHoneyfileDetail, toggleHoneyfileStatus } from "../api/client";
import type { HoneyfileDetail } from "../types/honeyfiles";
import { fileTypeIcon, honeyfileStatusPillStyle, HONEYFILE_STATUS_LABEL } from "../lib/honeyfileStatus";

interface Props {
  honeyfileId: number | null;
  onClose: () => void;
  onChanged: () => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="px-5 py-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
      <h3 className="text-[11px] tracking-wider uppercase font-semibold mb-3" style={{ color: "var(--tx-mute)" }}>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between text-[12.5px] py-1.5 gap-3">
      <span style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span
        className={`font-medium text-right truncate ${mono ? "font-mono text-[11px]" : ""}`}
        style={{ color: "var(--tx)" }}
      >
        {value}
      </span>
    </div>
  );
}

export default function HoneyfileDrawer({ honeyfileId, onClose, onChanged }: Props) {
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);
  const [data, setData] = useState<HoneyfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function load() {
    if (honeyfileId === null) return;
    setData(null);
    setError(null);
    fetchHoneyfileDetail(honeyfileId)
      .then(setData)
      .catch(() => setError("No se pudo cargar la información de este honeyfile."));
  }

  useEffect(() => {
    if (honeyfileId !== null) {
      setRender(true);
      load();
      const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
      return () => cancelAnimationFrame(raf);
    } else if (render) {
      setEntered(false);
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [honeyfileId]);

  useEffect(() => {
    if (!render) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [render, onClose]);

  if (!render || honeyfileId === null) return null;

  async function handleToggle() {
    setSaving(true);
    try {
      await toggleHoneyfileStatus(honeyfileId!);
      load();
      onChanged();
    } catch {
      setError("No se pudo cambiar el estado.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }}
      />
      <aside
        className="fixed top-0 right-0 h-screen w-full sm:w-[440px] z-50 flex flex-col"
        style={{
          background: "var(--surf)",
          borderLeft: "1px solid var(--line)",
          boxShadow: "-16px 0 40px rgba(0,0,0,.3)",
          transform: entered ? "translateX(0)" : "translateX(100%)",
          transition: "transform 220ms ease",
        }}
      >
        <div className="px-5 py-4 border-b flex items-start gap-3" style={{ borderColor: "var(--line-soft)" }}>
          <div className="min-w-0">
            <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
              Detalles del honeyfile
            </div>
            <div className="text-[17px] font-semibold mt-1 truncate flex items-center gap-2" style={{ color: "var(--tx)" }}>
              {data && <i className={fileTypeIcon(data.file_type)} style={{ fontSize: "16px", color: "var(--tx-mute)" }} />}
              {data?.file_name ?? "Cargando..."}
            </div>
            {data && (
              <div className="text-[11.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
                {data.hostname} · {data.agent_code}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-auto w-8 h-8 shrink-0 rounded-lg border grid place-items-center cursor-pointer"
            style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
          >
            <i className="ph ph-x" style={{ fontSize: "15px" }} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="px-5 py-6 text-center text-sm" style={{ color: "var(--crit)" }}>
              {error}
            </div>
          )}

          {!data && !error && (
            <div className="px-5 py-6 flex flex-col gap-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-4 rounded animate-pulse" style={{ background: "var(--surf3)" }} />
              ))}
            </div>
          )}

          {data && (
            <>
              {/* Estado principal */}
              <div className="px-5 py-4">
                <div
                  className="rounded-[10px] border p-3.5"
                  style={{
                    background: data.status === "TRIGGERED" ? "var(--crit-soft)" : "var(--surf2)",
                    borderColor: data.status === "TRIGGERED" ? "var(--crit)" : "var(--line)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Estado</span>
                    <span
                      className="text-[11px] font-bold tracking-wide px-2 py-0.5 rounded"
                      style={honeyfileStatusPillStyle(data.status)}
                    >
                      {HONEYFILE_STATUS_LABEL[data.status].toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Activaciones</div>
                      <div className="mt-1 text-[12px] font-semibold" style={{ color: data.activations_count > 0 ? "var(--crit)" : "var(--tx)" }}>
                        {data.activations_count}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Agente</div>
                      <div className="flex items-center gap-1.5 mt-1 text-[12px] font-medium" style={{ color: "var(--tx)" }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: data.is_online ? "var(--ok)" : "var(--off)" }} />
                        {data.is_online ? "Online" : "Offline"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <Section title="Información del archivo">
                <Field label="Nombre" value={data.file_name} />
                <Field label="Ruta" value={data.file_path} mono />
                <Field label="Tipo" value={data.file_type} />
                <Field label="Hash SHA-256" value={data.sha256_hash} mono />
                <Field label="Creado" value={data.created_at} />
                <Field label="Último chequeo" value={data.last_checked_at} />
              </Section>

              <Section title="Endpoint">
                <Field label="Hostname" value={data.hostname} />
                <Field label="Sistema operativo" value={`${data.operating_system} ${data.os_version}`.trim()} />
                <Field label="Dirección IP" value={data.ip_address} />
                <Field label="Identificador del agente" value={data.agent_code} />
                <Field label="Versión del agente" value={data.agent_version} />
              </Section>

              <Section title="Historial de activaciones">
                {data.activations.length === 0 ? (
                  <p className="text-[12px]" style={{ color: "var(--tx-mute)" }}>
                    Este honeyfile todavía no fue tocado. Sigue intacto.
                  </p>
                ) : (
                  <div className="flex flex-col gap-2.5">
                    {data.activations.map((a, i) => (
                      <div key={i} className="flex gap-2.5">
                        <i className="ph-fill ph-warning" style={{ fontSize: "13px", color: "var(--crit)", marginTop: "2px" }} />
                        <div className="min-w-0">
                          <div className="text-[12px] font-medium" style={{ color: "var(--tx)" }}>{a.operation}</div>
                          <div className="text-[11px]" style={{ color: "var(--tx-mute)" }}>
                            {a.process_name} (PID {a.process_id})
                          </div>
                          <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{a.detected_at}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              <div className="px-5 py-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
                <button
                  disabled={saving}
                  onClick={handleToggle}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold cursor-pointer disabled:opacity-50"
                  style={
                    data.status === "INACTIVE"
                      ? { border: "1px solid var(--ok)", color: "var(--ok)", background: "var(--ok-soft)" }
                      : { border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }
                  }
                >
                  <i className={data.status === "INACTIVE" ? "ph ph-play" : "ph ph-pause"} style={{ fontSize: "15px" }} />
                  {data.status === "INACTIVE" ? "Reactivar honeyfile" : "Desactivar honeyfile"}
                </button>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
