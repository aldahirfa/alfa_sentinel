import { useEffect, useState } from "react";
import { fetchAlertDrawer } from "../api/client";
import type { IncidenteDrawerData } from "../types/alerts";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import type { AlertStatus } from "../types/alerts";

interface Props {
  alertId: number | null;
  onClose: () => void;
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

export default function AlertDrawer({ alertId, onClose }: Props) {
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);
  const [data, setData] = useState<IncidenteDrawerData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (alertId !== null) {
      setRender(true);
      setData(null);
      setError(null);
      fetchAlertDrawer(alertId)
        .then(setData)
        .catch(() => setError("No se pudo cargar la información de esta alerta."));
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
        className="fixed top-0 right-0 h-screen w-full sm:w-[440px] z-50 flex flex-col"
        style={{
          background: "var(--surf)",
          borderLeft: "1px solid var(--line)",
          boxShadow: "-16px 0 40px rgba(0,0,0,.3)",
          transform: entered ? "translateX(0)" : "translateX(100%)",
          transition: "transform 220ms ease",
        }}
      >
        {/* Encabezado */}
        <div className="px-5 py-4 border-b flex items-start gap-3" style={{ borderColor: "var(--line-soft)" }}>
          <div className="min-w-0">
            <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
              Detalles de la alerta
            </div>
            <div className="text-[17px] font-semibold mt-1 truncate" style={{ color: "var(--tx)" }}>
              {data?.title ?? "Cargando..."}
            </div>
            {data && (
              <div className="text-[11.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
                {data.code} · {data.hostname}
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
                    background: data.severity === "CRITICAL" ? "var(--crit-soft)" : "var(--surf2)",
                    borderColor: data.severity === "CRITICAL" ? "var(--crit)" : "var(--line)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Severidad</span>
                    {data.severity && (
                      <span
                        className="text-[11px] font-bold tracking-wide px-2 py-0.5 rounded"
                        style={severityPillStyle(data.severity)}
                      >
                        {SEVERITY_LABEL[data.severity].toUpperCase()}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Estado</div>
                      <div className="mt-1">
                        <span
                          className="text-[10.5px] font-medium px-2 py-0.5 rounded inline-block"
                          style={statusPillStyle(data.status as AlertStatus)}
                        >
                          {data.status_label}
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Risk score</div>
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

              {/* Incidente relacionado */}
              <Section title="Incidente relacionado">
                {data.incident_id ? (
                  <a
                    href={`/incidentes/${data.incident_id}`}
                    className="flex items-center justify-center gap-1.5 w-full py-2 rounded-lg text-[12px] font-medium no-underline"
                    style={{ border: "1px solid var(--brand)", color: "var(--brand)" }}
                  >
                    Ver incidente #{data.incident_id}
                    <i className="ph ph-arrow-right text-[13px]" />
                  </a>
                ) : (
                  <p className="text-[12px]" style={{ color: "var(--tx-mute)" }}>
                    Esta alerta no forma parte de un incidente agrupado.
                  </p>
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
                  <div className="flex flex-col gap-3">
                    {data.timeline.map((item, i) => (
                      <div key={i} className="flex gap-2.5">
                        <i
                          className={item.kind === "honeyfile" ? "ph-fill ph-file-lock" : "ph ph-activity"}
                          style={{ fontSize: "13px", color: "var(--tx-dim)", marginTop: "2px" }}
                        />
                        <div className="min-w-0">
                          <div className="text-[12px] font-medium" style={{ color: "var(--tx)" }}>{item.label}</div>
                          {item.detail && (
                            <div className="text-[11px] truncate" style={{ color: "var(--tx-mute)" }}>{item.detail}</div>
                          )}
                          <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{item.at}</div>
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
    </>
  );
}
