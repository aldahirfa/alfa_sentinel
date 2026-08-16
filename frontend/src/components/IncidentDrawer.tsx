import { useEffect, useState } from "react";
import {
  assignIncident,
  classifyIncident,
  escalateAlertToIncident,
  fetchIncidenteDrawer,
  updateIncidentStatus,
} from "../api/client";
import type { IncidenteDrawerData } from "../types/alerts";
import type { AssignableUser, IncidentClassification, IncidentStatus, ItemKind } from "../types/incidentes";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { statusPillStyle } from "../lib/alertStatus";
import type { AlertStatus } from "../types/alerts";
import { INCIDENT_CLASSIFICATION_LABEL, INCIDENT_STATUS_LABEL } from "../lib/incidentStatus";

interface Props {
  selected: { kind: ItemKind; id: number } | null;
  assignableUsers: AssignableUser[];
  onClose: () => void;
  onChanged: () => void;
  // Navega a Alertas y abre la alerta de origen de este incidente.
  onViewAlert: (id: number) => void;
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

const selectStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line)",
  color: "var(--tx)",
};

export default function IncidentDrawer({ selected, assignableUsers, onClose, onChanged, onViewAlert }: Props) {
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);
  const [data, setData] = useState<IncidenteDrawerData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  function load() {
    if (!selected) return;
    setData(null);
    setError(null);
    fetchIncidenteDrawer(selected.kind, selected.id)
      .then(setData)
      .catch(() => setError("No se pudo cargar la información de este elemento."));
  }

  useEffect(() => {
    if (selected !== null) {
      setRender(true);
      setActionError(null);
      load();
      const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
      return () => cancelAnimationFrame(raf);
    } else if (render) {
      setEntered(false);
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  useEffect(() => {
    if (!render) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [render, onClose]);

  if (!render || !selected) return null;

  async function runAction(fn: () => Promise<unknown>) {
    setSaving(true);
    setActionError(null);
    try {
      await fn();
      load();
      onChanged();
    } catch {
      setActionError("No se pudo guardar el cambio.");
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
              {selected.kind === "incident" ? "Detalles del incidente" : "Detalles de la alerta"}
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
              {actionError && (
                <div className="mx-5 mt-4 rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                  {actionError}
                </div>
              )}

              {/* Estado principal */}
              <div className="px-5 py-4">
                <div
                  className="rounded-xl border p-4 shadow-sm"
                  style={{
                    background: data.severity === "CRITICAL" ? "var(--crit-fill)" : "var(--surf2)",
                    borderColor: data.severity === "CRITICAL" ? "var(--crit-soft)" : "var(--line-soft)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Severidad</span>
                    {data.severity && (
                      <span
                        className="text-[11px] font-bold tracking-wide px-2.5 py-0.5 rounded-full"
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
                        {selected.kind === "incident" ? (
                          <select
                            value={data.status}
                            disabled={saving}
                            onChange={(e) => runAction(() => updateIncidentStatus(selected.id, e.target.value as IncidentStatus))}
                            className="text-[10.5px] font-medium px-1.5 py-0.5 rounded outline-none cursor-pointer"
                            style={selectStyle}
                          >
                            {Object.entries(INCIDENT_STATUS_LABEL).map(([k, v]) => (
                              <option key={k} value={k}>{v}</option>
                            ))}
                          </select>
                        ) : (
                          <span
                            className="text-[10.5px] font-bold tracking-wide px-2.5 py-0.5 rounded-full inline-block"
                            style={{ ...statusPillStyle(data.status as AlertStatus), border: `1px solid ${statusPillStyle(data.status as AlertStatus).color}` }}
                          >
                            {data.status_label}
                          </span>
                        )}
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

              {/* Reglas asociadas -- solo llega itemizado para una alerta suelta */}
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

              {/* Gestión del caso -- solo para incidentes agrupados */}
              {selected.kind === "incident" && (
                <Section title="Gestión del caso">
                  <div className="flex items-center justify-between text-[12.5px] py-1.5">
                    <span style={{ color: "var(--tx-mute)" }}>Responsable</span>
                    <select
                      value={data.assigned_to ?? ""}
                      disabled={saving}
                      onChange={(e) =>
                        runAction(() => assignIncident(selected.id, e.target.value ? Number(e.target.value) : null))
                      }
                      className="text-[12px] font-medium px-2 py-1 rounded outline-none cursor-pointer max-w-[190px]"
                      style={selectStyle}
                    >
                      <option value="">Sin asignar</option>
                      {assignableUsers.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center justify-between text-[12.5px] py-1.5">
                    <span style={{ color: "var(--tx-mute)" }}>Clasificación</span>
                    <select
                      value={data.classification ?? ""}
                      disabled={saving}
                      onChange={(e) => runAction(() => classifyIncident(selected.id, e.target.value as IncidentClassification))}
                      className="text-[12px] font-medium px-2 py-1 rounded outline-none cursor-pointer max-w-[190px]"
                      style={selectStyle}
                    >
                      <option value="" disabled>Sin clasificar</option>
                      {Object.entries(INCIDENT_CLASSIFICATION_LABEL).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                </Section>
              )}

              {/* Alerta de origen -- la primera alerta (por fecha) que
                  quedó vinculada a este incidente, sea porque el motor
                  automático lo generó o porque un analista la escaló
                  a mano desde Alertas. Permite volver a esa alerta sin
                  duplicar toda su información acá. */}
              {selected.kind === "incident" && data.origin_alert && (
                <Section title="Alerta de origen">
                  <div className="rounded-[9px] p-2.5 flex flex-col gap-1.5" style={{ background: "var(--surf2)" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-medium" style={{ color: "var(--tx)" }}>
                        {data.origin_alert.code}
                      </span>
                      {data.origin_alert.severity && (
                        <span
                          className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full"
                          style={severityPillStyle(data.origin_alert.severity)}
                        >
                          {SEVERITY_LABEL[data.origin_alert.severity].toUpperCase()}
                        </span>
                      )}
                    </div>
                    <Field
                      label="Risk score"
                      value={data.origin_alert.risk_score !== null ? data.origin_alert.risk_score.toFixed(1) : "—"}
                    />
                    <Field label="Endpoint" value={data.hostname} />
                  </div>
                  <button
                    onClick={() => onViewAlert(data.origin_alert!.id)}
                    className="mt-2.5 flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg text-[12.5px] font-bold cursor-pointer border transition-premium btn-hover shadow-sm"
                    style={{ borderColor: "var(--brand)", color: "var(--brand)", background: "transparent" }}
                  >
                    Ver alerta original
                    <i className="ph-fill ph-arrow-right text-[14px]" />
                  </button>
                </Section>
              )}

              {/* Escalar a incidente -- solo para una alerta suelta sin incidente todavía */}
              {selected.kind === "alert" && (
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
                    <>
                      <p className="text-[12px] mb-2.5" style={{ color: "var(--tx-mute)" }}>
                        Esta alerta todavía no forma parte de un incidente agrupado.
                      </p>
                      <button
                        disabled={saving}
                        onClick={() => runAction(() => escalateAlertToIncident(selected.id))}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[13px] font-bold cursor-pointer disabled:opacity-50 border transition-premium btn-hover shadow-sm"
                        style={{ borderColor: "var(--brand)", color: "var(--brand)", background: "var(--brand-fill)" }}
                      >
                        <i className="ph-fill ph-siren" style={{ fontSize: "15px" }} />
                        Escalar a incidente
                      </button>
                    </>
                  )}
                </Section>
              )}

              {/* Actividad relacionada -- correlación aproximada por
                  ventana de tiempo, no existe una relación directa
                  alerta/incidente -> evento en la base de datos. */}
              {data.timeline.length > 0 && (
                <Section title="Actividad relacionada">
                  <p className="text-[10.5px] mb-2.5" style={{ color: "var(--tx-mute)" }}>
                    Eventos cercanos en el tiempo (correlación aproximada, no un vínculo directo).
                  </p>
                  <div className="flex flex-col gap-0 relative before:absolute before:inset-y-2 before:left-[5px] before:w-px before:bg-[var(--line)]">
                    {data.timeline.map((item, i) => (
                      <div key={i} className="flex gap-3.5 relative py-2">
                        <div className="w-[11px] h-[11px] rounded-full mt-1 z-10 shrink-0 ring-4 ring-[var(--surf)]" style={{ background: item.kind === "honeyfile" ? "var(--warn)" : "var(--tx-mute)" }} />
                        <div className="min-w-0">
                          <div className="text-[12.5px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>{item.label}</div>
                          {item.detail && (
                            <div className="text-[11px] mt-0.5 truncate" style={{ color: "var(--tx-mute)" }}>{item.detail}</div>
                          )}
                          <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-dim)" }}>{item.at}</div>
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

              {/* Acción de aislamiento -- mismo estado honesto que en
                  EndpointDrawer: el agente no tiene canal de comandos
                  remotos, así que no hay forma real de aislarlo. */}
              <div className="px-5 py-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
                <button
                  disabled
                  title="ALFA-Sentinel no puede aislar un host todavía: el agente no tiene forma de recibir ni ejecutar un comando remoto."
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold cursor-not-allowed opacity-50"
                  style={{ border: "1px solid var(--crit)", color: "var(--crit)", background: "var(--crit-soft)" }}
                >
                  <i className="ph ph-plugs" style={{ fontSize: "15px" }} />
                  Aislar endpoint
                </button>
                <p className="text-[10.5px] mt-2 text-center" style={{ color: "var(--tx-mute)" }}>
                  El aislamiento remoto todavía no está implementado en el agente.
                </p>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
