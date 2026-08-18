import { useEffect, useState } from "react";
import { fetchAlertDrawer } from "../api/client";
import type { IncidenteDrawerData } from "../types/alerts";
import { severityPillStyle } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import type { AlertStatus } from "../types/alerts";
import EscalateAlertModal from "./EscalateAlertModal";

interface Props {
  alertId: number | null;
  onClose: () => void;
  // Refresca la lista/resumen de Alertas después de escalar (mismo
  // patrón que onChanged en IncidentDrawer.tsx).
  onChanged: () => void;
  // Navega a Incidentes y abre el incidente asociado a esta alerta.
  onViewIncident: (id: number) => void;
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

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-[12.5px] py-1.5">
      <span style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span className="font-medium text-right" style={{ color: "var(--tx)" }}>{value}</span>
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

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }}
      />
      <aside
        className="fixed top-0 right-0 h-screen w-full sm:w-[460px] z-50 flex flex-col shadow-2xl"
        style={{
          background: "var(--surf)",
          borderLeft: "1px solid var(--line)",
          transform: entered ? "translateX(0)" : "translateX(100%)",
          transition: "transform 220ms ease",
        }}
      >
        {/* Encabezado */}
        <div className="px-5 py-4 border-b flex items-start gap-4" style={{ borderColor: "var(--line-soft)" }}>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
              Detalles de la alerta
            </div>
            <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
              {data?.title ?? "Cargando..."}
            </div>
            {data && (
              <div className="text-[11.5px] mt-1.5 font-medium" style={{ color: "var(--tx-mute)" }}>
                {data.code} · {data.hostname}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-auto w-8 h-8 shrink-0 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
            style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
          >
            <i className="ph-fill ph-x" style={{ fontSize: "15px" }} />
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
                  className="rounded-xl border p-4 shadow-sm"
                  style={{
                    background: data.severity === "CRÍTICO" ? "var(--crit-fill)" : "var(--surf2)",
                    borderColor: data.severity === "CRÍTICO" ? "var(--crit-soft)" : "var(--line-soft)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Severidad</span>
                    {data.severity && (
                      <span
                        className="text-[11px] font-bold tracking-wide px-2.5 py-0.5 rounded-full"
                        style={severityPillStyle(data.severity)}
                      >
                        {data.severity.toUpperCase()}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Estado</div>
                      <div className="mt-1">
                        <span
                          className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full inline-block"
                          style={{ ...statusPillStyle(data.status as AlertStatus), border: `1px solid ${statusPillStyle(data.status as AlertStatus).color}` }}
                        >
                          {data.status_label}
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Puntos de riesgo</div>
                      <div className="mt-1 text-[12px] font-semibold tabular-nums" style={{ color: "var(--tx)" }}>
                        {data.risk_score !== null ? data.risk_score.toFixed(1) : "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Detecciones</div>
                      <div className="mt-1 text-[12px] font-medium" style={{ color: "var(--tx)" }}>{data.detection_count}</div>
                    </div>
                  </div>
                </div>
              </div>

              {data.description && (
                <Section title="Descripción">
                  <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--tx-dim)" }}>{data.description}</p>
                </Section>
              )}

              {/* Endpoint */}
              <Section title="Endpoint afectado">
                <Field label="Hostname" value={data.hostname} />
                <Field label="Sistema operativo" value={data.operating_system} />
                <Field label="Dirección IP" value={data.ip_address} />
                <Field
                  label="Conectividad"
                  value={
                    <span style={{ color: data.is_online ? "var(--ok)" : "var(--off)" }}>
                      {data.is_online ? "Online" : "Offline"}
                    </span>
                  }
                />
                {data.is_honeyfile && (
                  <Field label="Origen" value={<span style={{ color: "var(--warn)" }}>Honeyfile</span>} />
                )}
              </Section>

              {/* Reglas asociadas */}
              {data.rules.length > 0 && (
                <Section title="Reglas asociadas">
                  <div className="flex flex-col gap-2">
                    {data.rules.map((r, i) => (
                      <div key={i} className="rounded-[9px] p-2.5 flex items-center justify-between" style={{ background: "var(--surf2)" }}>
                        <div>
                          <div className="text-[12px] font-medium" style={{ color: "var(--tx)" }}>{r.rule_name}</div>
                          <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{r.matched_at}</div>
                        </div>
                        <div className="text-[12px] font-semibold tabular-nums" style={{ color: "var(--tx-dim)" }}>
                          +{r.weight_applied.toFixed(1)}
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Proceso involucrado (2026-08-18, ver PENDIENTES.md,
                  "Corrección definitiva en la lógica y presentación de
                  ALERTAS", sección 5) -- correlación real por ventana
                  de tiempo, nunca inventado: si el agente no pudo
                  atribuir el proceso (o el dato simplemente no existe
                  en la base, como 'ruta'/'usuario' hoy), se muestra
                  "No disponible" en vez de fabricar un valor. */}
              <Section title="Proceso involucrado">
                <Field label="Proceso" value={data.process.process_name ?? "No disponible"} />
                <Field label="PID" value={data.process.process_id !== null ? data.process.process_id : "No disponible"} />
                <Field label="Ruta" value={data.process.executable_path ?? "No disponible"} />
                <Field label="Usuario" value={data.process.username ?? "No disponible"} />
              </Section>

              {/* Incidente relacionado -- el sistema tiene su propio
                  mecanismo automático de escalamiento (motor
                  heurístico), pero un analista puede decidir que una
                  alerta amerita tratarse como incidente aunque el
                  sistema todavía no la haya escalado. Ambos caminos
                  terminan en el mismo lugar: alerts.incident_id. */}
              <Section title="Incidente relacionado">
                {data.incident_id ? (
                  <>
                    <div className="flex items-center justify-between mb-2.5">
                      <span className="text-[12px]" style={{ color: "var(--tx-mute)" }}>Incidente asociado</span>
                      <span className="text-[12.5px] font-semibold tabular-nums" style={{ color: "var(--tx)" }}>
                        INC-{String(data.incident_id).padStart(5, "0")}
                      </span>
                    </div>
                    <button
                      onClick={() => onViewIncident(data.incident_id!)}
                      className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg text-[12.5px] font-bold cursor-pointer border transition-premium btn-hover shadow-sm"
                      style={{ borderColor: "var(--brand)", color: "var(--brand)", background: "transparent" }}
                    >
                      Ver incidente
                      <i className="ph-fill ph-arrow-right text-[14px]" />
                    </button>
                  </>
                ) : (
                  <>
                    <p className="text-[12px] mb-2.5" style={{ color: "var(--tx-mute)" }}>
                      Sin incidente. Esta alerta todavía no forma parte de un caso agrupado.
                    </p>
                    <button
                      onClick={() => setShowEscalate(true)}
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[13px] font-bold cursor-pointer border transition-premium btn-hover shadow-sm"
                      style={{ borderColor: "var(--brand)", color: "var(--brand)", background: "var(--brand-fill)" }}
                    >
                      <i className="ph-fill ph-siren" style={{ fontSize: "15px" }} />
                      Escalar a incidente
                    </button>
                  </>
                )}
              </Section>

              {/* Actividad relacionada -- correlación aproximada por
                  ventana de tiempo, no existe una relación directa
                  alerta -> evento en la base de datos. */}
              {data.timeline.length > 0 && (
                <Section title="Actividad relacionada">
                  <p className="text-[10.5px] mb-2.5" style={{ color: "var(--tx-mute)" }}>
                    Eventos cercanos en el tiempo a esta alerta (correlación aproximada, no un vínculo directo).
                  </p>
                  <div className="flex flex-col gap-0 relative before:absolute before:inset-y-2 before:left-[5px] before:w-px before:bg-[var(--line)]">
                    {data.timeline.map((item, i) => (
                      <div key={i} className="flex gap-3.5 relative py-2">
                        <div className="w-[11px] h-[11px] rounded-full mt-1 z-10 shrink-0 ring-4 ring-[var(--surf)]" style={{ background: item.kind === "honeyfile" ? "var(--warn)" : "var(--tx-mute)" }} />
                        <div className="min-w-0">
                          <div className="text-[12.5px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>{item.label}</div>
                          {item.detail && (
                            <div className="text-[11px] mt-0.5 font-medium truncate" style={{ color: "var(--tx-mute)" }}>{item.detail}</div>
                          )}
                          <div className="text-[10.5px] mt-1 font-medium" style={{ color: "var(--tx-dim)" }}>{item.at}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {data.resolved_at && (
                <Section title="Resolución">
                  <Field label="Resuelta el" value={data.resolved_at} />
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
