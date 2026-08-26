import { useEffect, useState } from "react";
import { fetchAlertDrawer } from "../api/client";
import type { IncidenteDrawerData, AlertStatus } from "../types/alerts";
import { severityPillStyle, SEVERITY_VAR } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import EscalateAlertModal from "./EscalateAlertModal";

interface Props {
  alertId: number | null;
  onClose: () => void;
  onChanged: () => void;
  onViewIncident: (id: number) => void;
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <section className="px-5 py-5 border-t" style={{ borderColor: "var(--line-soft)" }}>
      <div className="flex items-center gap-2 mb-3.5">
        <span className="w-7 h-7 rounded-lg grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className={icon} style={{ fontSize: "13px" }} />
        </span>
        <h3 className="text-[9.5px] tracking-[.14em] uppercase font-bold m-0" style={{ color: "var(--tx-mute)" }}>
          {title}
        </h3>
      </div>
      {children}
    </section>
  );
}

function Field({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[135px_minmax(0,1fr)] gap-3 items-start py-2.5 border-b last:border-b-0" style={{ borderColor: "var(--line-soft)" }}>
      <span className="text-[10px]" style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span className={`text-[11px] font-medium text-right break-all ${mono ? "mono-data" : ""}`} style={{ color: "var(--tx)" }}>{value}</span>
    </div>
  );
}

export default function AlertDrawer({ alertId, onClose, onChanged, onViewIncident }: Props) {
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);
  const [data, setData] = useState<IncidenteDrawerData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEscalate, setShowEscalate] = useState(false);

  function loadDrawer(id: number) {
    setData(null);
    setError(null);
    fetchAlertDrawer(id)
      .then(setData)
      .catch(() => setError("No se pudo cargar la información de esta alerta."));
  }

  useEffect(() => {
    if (alertId !== null) {
      setRender(true);
      loadDrawer(alertId);
      const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
      return () => cancelAnimationFrame(raf);
    } else if (render) {
      setEntered(false);
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
  }, [alertId]);

  useEffect(() => {
    if (!render) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [render, onClose]);

  if (!render) return null;

  const severityColor = data?.severity ? SEVERITY_VAR[data.severity] : "var(--brand)";

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40"
        style={{
          background: "rgba(2, 8, 18, .68)",
          backdropFilter: "blur(3px)",
          opacity: entered ? 1 : 0,
          transition: "opacity 200ms ease",
        }}
      />

      <aside
        className="fixed top-0 right-0 h-screen w-full sm:w-[520px] z-50 flex flex-col"
        style={{
          background: "var(--surf)",
          borderLeft: "1px solid var(--line)",
          boxShadow: "var(--shadow-lg)",
          transform: entered ? "translateX(0)" : "translateX(100%)",
          transition: "transform 220ms cubic-bezier(.16,1,.3,1)",
        }}
      >
        <div className="relative px-5 py-5 border-b overflow-hidden" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(135deg, var(--surf2), var(--surf))" }}>
          <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: severityColor }} />
          <div className="absolute -right-16 -top-20 w-52 h-52 rounded-full" style={{ background: data?.severity === "CRÍTICO" ? "var(--crit-soft)" : "var(--brand-soft)", filter: "blur(35px)", opacity: .65 }} />

          <div className="relative z-[1] flex items-start gap-4">
            <div
              className="w-11 h-11 rounded-2xl grid place-items-center shrink-0 border"
              style={{ background: `color-mix(in srgb, ${severityColor} 12%, var(--surf2))`, borderColor: `color-mix(in srgb, ${severityColor} 24%, var(--line-soft))`, color: severityColor }}
            >
              <i className={data?.severity === "CRÍTICO" ? "ph-fill ph-warning-octagon" : "ph ph-waveform"} style={{ fontSize: "20px" }} />
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-[9px] tracking-[.17em] uppercase font-bold" style={{ color: "var(--brand)" }}>
                Investigación de alerta
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-[-.025em] leading-snug" style={{ color: "var(--tx)" }}>
                {data?.title ?? "Cargando alerta..."}
              </div>
              {data && (
                <div className="flex items-center gap-2 mt-2 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>
                  <span className="mono-data">{data.code}</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><i className="ph ph-desktop-tower" /> {data.hostname}</span>
                </div>
              )}
            </div>

            <button
              onClick={onClose}
              aria-label="Cerrar detalle"
              className="w-9 h-9 shrink-0 rounded-xl border grid place-items-center cursor-pointer transition-premium btn-hover"
              style={{ borderColor: "var(--line-soft)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="px-5 py-10 text-center">
              <div className="w-12 h-12 rounded-2xl grid place-items-center mx-auto mb-3" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
              </div>
              <div className="text-[12px] font-semibold" style={{ color: "var(--crit)" }}>{error}</div>
            </div>
          )}

          {!data && !error && (
            <div className="px-5 py-6 flex flex-col gap-3">
              <div className="h-28 rounded-2xl animate-pulse" style={{ background: "var(--surf2)" }} />
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-16 rounded-xl animate-pulse" style={{ background: "var(--surf2)" }} />
              ))}
            </div>
          )}

          {data && (
            <>
              <div className="p-5">
                <div
                  className="rounded-2xl border p-4 relative overflow-hidden"
                  style={{
                    background: data.severity === "CRÍTICO" ? "linear-gradient(135deg, var(--crit-fill), var(--surf2))" : "linear-gradient(135deg, var(--brand-fill), var(--surf2))",
                    borderColor: data.severity === "CRÍTICO" ? "var(--crit-soft)" : "var(--line-soft)",
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[9px] uppercase tracking-[.13em] font-bold" style={{ color: "var(--tx-mute)" }}>Prioridad de análisis</div>
                      <div className="text-[22px] font-bold mt-1 tracking-[-.04em]" style={{ color: severityColor }}>
                        {data.risk_score !== null ? data.risk_score.toFixed(1) : "—"}
                        <span className="text-[9px] font-medium ml-1" style={{ color: "var(--tx-mute)" }}>puntos de riesgo</span>
                      </div>
                    </div>
                    <span className="text-[9px] font-bold tracking-[.08em] px-2.5 py-1 rounded-md" style={severityPillStyle(data.severity)}>
                      {data.severity.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
                    <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf)", border: "1px solid var(--line-soft)" }}>
                      <div className="text-[8.5px] uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Estado</div>
                      <div className="mt-1.5">
                        <span className="inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-md" style={{ ...statusPillStyle(data.status as AlertStatus), border: `1px solid ${statusPillStyle(data.status as AlertStatus).color}` }}>
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusPillStyle(data.status as AlertStatus).color }} />
                          {data.status_label}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--surf)", border: "1px solid var(--line-soft)" }}>
                      <div className="text-[8.5px] uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Señales correlacionadas</div>
                      <div className="text-[16px] font-bold mt-1 tabular-nums" style={{ color: "var(--tx)" }}>{data.detection_count}</div>
                    </div>
                  </div>
                </div>
              </div>

              {data.description && (
                <Section title="Descripción de la detección" icon="ph ph-text-align-left">
                  <p className="text-[11px] leading-[1.7] m-0" style={{ color: "var(--tx-dim)" }}>{data.description}</p>
                </Section>
              )}

              <Section title="Endpoint afectado" icon="ph ph-desktop-tower">
                <div className="rounded-xl px-3.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                  <Field label="Hostname" value={data.hostname} mono />
                  <Field label="Sistema operativo" value={data.operating_system} />
                  <Field label="Dirección IP" value={data.ip_address} mono />
                  <Field label="Conectividad" value={<span className="inline-flex items-center gap-1.5" style={{ color: data.is_online ? "var(--ok)" : "var(--off)" }}><span className="w-1.5 h-1.5 rounded-full" style={{ background: data.is_online ? "var(--ok)" : "var(--off)" }} />{data.is_online ? "Online" : "Offline"}</span>} />
                  {data.is_honeyfile && <Field label="Origen" value={<span style={{ color: "var(--warn)" }}>Activación de honeyfile</span>} />}
                </div>
              </Section>

              {data.rules.length > 0 && (
                <Section title="Señales y reglas asociadas" icon="ph ph-list-checks">
                  <div className="flex flex-col gap-2">
                    {data.rules.map((r, i) => (
                      <div key={i} className="rounded-xl p-3 flex items-center gap-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                        <div className="w-8 h-8 rounded-lg grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                          <i className="ph ph-waveform" style={{ fontSize: "13px" }} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-[10.5px] font-semibold truncate" style={{ color: "var(--tx)" }}>{r.rule_name}</div>
                          <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{r.matched_at}</div>
                        </div>
                        <div className="text-[11px] font-bold tabular-nums" style={{ color: "var(--brand)" }}>+{r.weight_applied.toFixed(1)}</div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              <Section title="Proceso involucrado" icon="ph ph-terminal-window">
                <div className="rounded-xl px-3.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                  <Field label="Proceso" value={data.process.process_name ?? "No disponible"} mono />
                  <Field label="PID" value={data.process.process_id !== null ? data.process.process_id : "No disponible"} mono />
                  <Field label="Ruta" value={data.process.executable_path ?? "No disponible"} mono />
                  <Field label="Usuario" value={data.process.username ?? "No disponible"} />
                </div>
              </Section>

              <Section title="Gestión del incidente" icon="ph ph-siren">
                {data.incident_id ? (
                  <div className="rounded-2xl p-4" style={{ background: "var(--brand-fill)", border: "1px solid var(--brand-soft)" }}>
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div>
                        <div className="text-[9px] uppercase tracking-[.12em] font-bold" style={{ color: "var(--tx-mute)" }}>Incidente asociado</div>
                        <div className="mono-data text-[14px] font-bold mt-1" style={{ color: "var(--tx)" }}>INC-{String(data.incident_id).padStart(5, "0")}</div>
                      </div>
                      <i className="ph-fill ph-siren" style={{ fontSize: "22px", color: "var(--brand)" }} />
                    </div>
                    <button onClick={() => onViewIncident(data.incident_id!)} className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-[10.5px] font-semibold cursor-pointer border transition-premium btn-hover" style={{ borderColor: "var(--brand-soft)", color: "#fff", background: "var(--brand)" }}>
                      Abrir incidente
                      <i className="ph ph-arrow-up-right" style={{ fontSize: "12px" }} />
                    </button>
                  </div>
                ) : (
                  <div className="rounded-2xl p-4" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                    <div className="text-[11px] font-semibold" style={{ color: "var(--tx)" }}>Esta alerta aún no forma parte de un incidente.</div>
                    <p className="text-[9.5px] leading-relaxed mt-1.5 mb-3" style={{ color: "var(--tx-mute)" }}>
                      El analista puede escalarla manualmente si la evidencia y el contexto justifican abrir un caso de investigación.
                    </p>
                    <button onClick={() => setShowEscalate(true)} className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-[10.5px] font-semibold cursor-pointer border transition-premium btn-hover" style={{ borderColor: "var(--brand-soft)", color: "#fff", background: "var(--brand)" }}>
                      <i className="ph-fill ph-siren" style={{ fontSize: "13px" }} />
                      Escalar a incidente
                    </button>
                  </div>
                )}
              </Section>

              {data.timeline.length > 0 && (
                <Section title="Actividad relacionada" icon="ph ph-clock-counter-clockwise">
                  <div className="text-[9px] mb-3 leading-relaxed" style={{ color: "var(--tx-mute)" }}>
                    Eventos cercanos en el tiempo a esta alerta. La correlación es aproximada y no representa una relación directa en la base de datos.
                  </div>
                  <div className="flex flex-col relative before:absolute before:inset-y-2 before:left-[6px] before:w-px before:bg-[var(--line)]">
                    {data.timeline.map((item, i) => (
                      <div key={i} className="flex gap-3.5 relative py-2.5">
                        <div className="w-[13px] h-[13px] rounded-full mt-0.5 z-10 shrink-0 ring-4 ring-[var(--surf)]" style={{ background: item.kind === "honeyfile" ? "var(--warn)" : "var(--brand)" }} />
                        <div className="min-w-0">
                          <div className="text-[10.5px] font-semibold" style={{ color: "var(--tx)" }}>{item.label}</div>
                          {item.detail && <div className="text-[9.5px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>{item.detail}</div>}
                          <div className="text-[9px] mt-1 mono-data" style={{ color: "var(--tx-dim)" }}>{item.at}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {data.resolved_at && (
                <Section title="Resolución" icon="ph ph-check-circle">
                  <div className="rounded-xl px-3.5" style={{ background: "var(--ok-soft)", border: "1px solid color-mix(in srgb, var(--ok) 20%, var(--line-soft))" }}>
                    <Field label="Resuelta el" value={data.resolved_at} mono />
                  </div>
                </Section>
              )}
            </>
          )}
        </div>
      </aside>

      {showEscalate && data && (
        <EscalateAlertModal
          alert={data}
          onClose={() => setShowEscalate(false)}
          onEscalated={() => {
            setShowEscalate(false);
            loadDrawer(data.id);
            onChanged();
          }}
        />
      )}
    </>
  );
}
