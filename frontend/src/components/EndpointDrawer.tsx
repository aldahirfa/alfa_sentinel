import { useEffect, useState } from "react";
import { fetchEndpointDrawer, isolateIncident, releaseIsolation } from "../api/client";
import type { EndpointDrawerData } from "../types/endpoints";
import { severityPillStyle } from "../lib/severity";
import {
  AGENT_HEALTH_LABEL,
  AGENT_HEALTH_VAR,
  CONN_STATUS_LABEL,
  CONN_STATUS_VAR,
} from "../lib/endpointStatus";
import type { ConnStatus } from "../types/endpoints";
import AgentRulesModal from "./AgentRulesModal";
import {
  ISOLATE_ICON_CLASS, RELEASE_ICON_CLASS, PENDING_ICON_CLASS, SPINNER_ICON_CLASS,
  ISOLATE_LABEL_FULL, RELEASE_LABEL_FULL, PENDING_LABEL_FULL, SENDING_LABEL,
  ISOLATE_TOOLTIP, RELEASE_TOOLTIP, confirmIsolate,
} from "../lib/isolationUi";

interface Props {
  endpointId: number | null;
  onClose: () => void;
}

function connStatusOf(d: EndpointDrawerData): ConnStatus {
  if (d.is_isolated) return "ISOLATED";
  return d.status === "ONLINE" ? "ONLINE" : "OFFLINE";
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

export default function EndpointDrawer({ endpointId, onClose }: Props) {
  const [render, setRender] = useState(false);
  const [entered, setEntered] = useState(false);
  const [data, setData] = useState<EndpointDrawerData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [isolating, setIsolating] = useState(false);
  const [isolateError, setIsolateError] = useState<string | null>(null);
  const [isolateRequested, setIsolateRequested] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [releaseError, setReleaseError] = useState<string | null>(null);
  const [releaseRequested, setReleaseRequested] = useState(false);

  async function handleIsolate() {
    if (!data?.active_incident_id || isolating) return;
    if (!confirmIsolate(data.hostname)) return;
    setIsolating(true);
    setIsolateError(null);
    try {
      await isolateIncident(data.active_incident_id);
      setIsolateRequested(true);
    } catch (err) {
      setIsolateError(err instanceof Error ? err.message : "No se pudo enviar la orden de aislamiento.");
    } finally {
      setIsolating(false);
    }
  }

  // Mismo backend/máquina de estados que "Liberar" en
  // IsolationsHistoryTable.tsx/CriticalIncidentsTable.tsx -- una sola
  // implementación (sección 13 de "ALFA_SENTINEL — CORRECCIÓN DE
  // TIEMPO REAL...", 2026-08-17, ver PENDIENTES.md).
  async function handleRelease() {
    if (!data?.isolation_id || releasing) return;
    setReleasing(true);
    setReleaseError(null);
    try {
      await releaseIsolation(data.isolation_id);
      setReleaseRequested(true);
    } catch (err) {
      setReleaseError(err instanceof Error ? err.message : "No se pudo enviar la orden de liberación.");
    } finally {
      setReleasing(false);
    }
  }

  useEffect(() => {
    if (endpointId !== null) {
      setRender(true);
      setData(null);
      setError(null);
      setIsolateError(null);
      setIsolateRequested(false);
      setReleaseError(null);
      setReleaseRequested(false);
      fetchEndpointDrawer(endpointId)
        .then(setData)
        .catch(() => setError("No se pudo cargar la información de este endpoint."));
      const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
      return () => cancelAnimationFrame(raf);
    } else if (render) {
      setEntered(false);
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
  }, [endpointId]);

  useEffect(() => {
    if (!render) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [render, onClose]);

  if (!render) return null;

  const connStatus = data ? connStatusOf(data) : null;

  // Timeline mínima, solo con eventos que realmente tenemos para este
  // endpoint (no existe un log unificado de actividad por endpoint
  // todavía -- ver PENDIENTES.md). Orden aproximado: lo más reciente
  // primero, el registro del endpoint siempre al final porque es,
  // por definición, el evento más viejo.
  type TimelineItem = { icon: string; color: string; label: string; detail: string; time: string };
  const timeline: TimelineItem[] = [];
  if (data) {
    if (data.latest_alert) {
      timeline.push({
        icon: "ph-fill ph-warning",
        color: String(severityPillStyle(data.latest_alert.severity).color ?? "var(--tx)"),
        label: "Alerta generada",
        detail: data.latest_alert.title,
        time: data.latest_alert.created_at,
      });
    }
    if (data.honeyfiles_violated_ago) {
      timeline.push({
        icon: "ph-fill ph-file-lock",
        color: "var(--warn)",
        label: "Honeyfile activado",
        detail: data.honeyfiles_violated_file || "",
        time: data.honeyfiles_violated_ago,
      });
    }
    timeline.push({
      icon: "ph ph-desktop-tower",
      color: "var(--ok)",
      label: "Endpoint registrado",
      detail: "",
      time: data.enrolled_at,
    });
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
          {data && (
            <i 
              className={data.operating_system.toLowerCase().includes("win") ? "ph-fill ph-windows-logo mt-1" : data.operating_system.toLowerCase().includes("linux") ? "ph-fill ph-linux-logo mt-1" : "ph-fill ph-desktop mt-1"} 
              style={{ fontSize: "28px", color: "var(--tx-dim)" }} 
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
              Detalles del endpoint
            </div>
            <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
              {data?.hostname ?? "Cargando..."}
            </div>
            {data && (
              <div className="text-[11.5px] mt-1.5 font-medium" style={{ color: "var(--tx-mute)" }}>
                {data.operating_system} {data.os_version} · {data.ip_address} · {data.agent_code}
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

          {data && connStatus && (
            <>
              {/* Estado principal */}
              <div className="px-5 py-4">
                <div
                  className="rounded-xl border p-4 shadow-sm"
                  style={{
                    background: data.risk_bucket === "CRÍTICO" ? "var(--crit-fill)" : "var(--surf2)",
                    borderColor: data.risk_bucket === "CRÍTICO" ? "var(--crit-soft)" : "var(--line-soft)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold" style={{ color: "var(--tx-mute)" }}>Nivel de riesgo</span>
                    <span
                      className="text-[11px] font-bold tracking-wide px-2.5 py-0.5 rounded-full"
                      style={severityPillStyle(data.risk_bucket)}
                    >
                      {data.risk_bucket.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Estado</div>
                      <div className="flex items-center gap-1.5 mt-1 text-[12px] font-medium" style={{ color: "var(--tx)" }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[connStatus] }} />
                        {CONN_STATUS_LABEL[connStatus]}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Agente</div>
                      <div className="flex items-center gap-1.5 mt-1 text-[12px] font-medium" style={{ color: "var(--tx)" }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: AGENT_HEALTH_VAR[data.agent_health] }} />
                        {AGENT_HEALTH_LABEL[data.agent_health]}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Última conexión</div>
                      <div className="mt-1 text-[12px] font-medium" style={{ color: "var(--tx)" }}>{data.last_seen_ago}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Información del endpoint */}
              <Section title="Información del endpoint">
                <Field label="Hostname" value={data.hostname} />
                <Field label="Sistema operativo" value={`${data.operating_system} ${data.os_version}`.trim()} />
                <Field label="Dirección IP" value={data.ip_address} />
                <Field label="Identificador del agente" value={data.agent_code} />
                <Field label="Versión del agente" value={data.agent_version} />
                <Field label="Fecha de registro" value={data.enrolled_at || "—"} />
                <Field label="Último heartbeat" value={data.last_seen_at} />
              </Section>

              {/* Estado de seguridad */}
              <Section title="Estado de seguridad">
                <Field
                  label="Alertas activas"
                  value={
                    <span style={{ color: data.alerts_active > 0 ? "var(--warn)" : "var(--tx)" }}>
                      {data.alerts_active}
                    </span>
                  }
                />
                <Field
                  label="Incidentes asociados"
                  value={`${data.incidents_total} (${data.incidents_active} activo${data.incidents_active === 1 ? "" : "s"})`}
                />
                {data.latest_alert && (
                  <div className="mt-3 rounded-xl border p-3.5 shadow-sm transition-premium hover:-translate-y-1" style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}>
                    <div className="flex items-center gap-2.5">
                      <span className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full" style={severityPillStyle(data.latest_alert.severity)}>
                        {data.latest_alert.severity.toUpperCase()}
                      </span>
                      <span className="text-[11.5px] font-medium" style={{ color: "var(--tx-mute)" }}>{data.latest_alert.created_at}</span>
                    </div>
                    <div className="text-[13px] font-bold tracking-tight mt-2" style={{ color: "var(--tx)" }}>{data.latest_alert.title}</div>
                    {data.latest_alert.rule_name && (
                      <div className="text-[11.5px] font-medium mt-1" style={{ color: "var(--tx-dim)" }}>
                        Indicador: {data.latest_alert.rule_name}
                      </div>
                    )}
                  </div>
                )}
              </Section>

              {/* Honeyfiles */}
              <Section title="Honeyfiles">
                {data.honeyfiles_total === 0 ? (
                  <p className="text-[12px]" style={{ color: "var(--tx-mute)" }}>
                    No hay información de honeyfiles disponible para este endpoint.
                  </p>
                ) : (
                  <>
                    <Field label="Honeyfiles desplegados" value={data.honeyfiles_total} />
                    <Field
                      label="Estado"
                      value={
                        data.honeyfiles_violated_file ? (
                          <span style={{ color: "var(--crit)" }}>Violada</span>
                        ) : (
                          <span style={{ color: "var(--ok)" }}>Intactas</span>
                        )
                      }
                    />
                    {data.honeyfiles_violated_file && (
                      <div className="mt-1.5 text-[11.5px]" style={{ color: "var(--tx-dim)" }}>
                        {data.honeyfiles_violated_file} · {data.honeyfiles_violated_ago}
                      </div>
                    )}
                  </>
                )}
              </Section>

              {/* Actividad reciente */}
              {timeline.length > 0 && (
                <Section title="Actividad reciente">
                  <div className="flex flex-col gap-0 relative before:absolute before:inset-y-2 before:left-[5px] before:w-px before:bg-[var(--line)]">
                    {timeline.map((item, i) => (
                      <div key={i} className="flex gap-3.5 relative py-2">
                        <div className="w-[11px] h-[11px] rounded-full mt-1 z-10 shrink-0 ring-4 ring-[var(--surf)]" style={{ background: item.color }} />
                        <div className="min-w-0">
                          <div className="text-[12.5px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>{item.label}</div>
                          {item.detail && (
                            <div className="text-[11px] mt-0.5 font-medium truncate" style={{ color: "var(--tx-mute)" }}>{item.detail}</div>
                          )}
                          <div className="text-[10.5px] mt-1 font-medium" style={{ color: "var(--tx-dim)" }}>{item.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Alertas */}
              <Section title="Alertas">
                  <a
                    href={`/detecciones?agent_id=${data.id}`}
                    className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg text-[12.5px] font-bold no-underline border transition-premium btn-hover shadow-sm"
                    style={{ borderColor: "var(--brand)", color: "var(--brand)", background: "transparent" }}
                  >
                    Ver alertas de este endpoint
                    <i className="ph-fill ph-arrow-right text-[14px]" />
                  </a>
              </Section>

              {/* Configuración de reglas por endpoint (2026-08-16, ver
                  PENDIENTES.md) -- override puntual sobre 'agent_rule',
                  reusa GET/PATCH/DELETE /api/agents/{agent_id}/rules.
                  data.id acá ES el agent_id: /api/endpoints/{agent_id}/drawer
                  devuelve agents.id, no endpoints.id (ver server/main.py). */}
              <Section title="Configuración de reglas">
                <button
                  onClick={() => setRulesModalOpen(true)}
                  className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg text-[12.5px] font-bold cursor-pointer border transition-premium btn-hover shadow-sm"
                  style={{ borderColor: "var(--line)", color: "var(--tx)", background: "var(--surf2)" }}
                >
                  <i className="ph-fill ph-sliders-horizontal" style={{ fontSize: "14px" }} />
                  Configurar reglas de este endpoint
                </button>
              </Section>

              {/* Acción de aislamiento -- disparo MANUAL real (2026-08-17,
                  ver PENDIENTES.md, "Aislamiento de host -- modo
                  development, laboratorio y producción"): usa el mismo
                  mecanismo de backend/agente que el automático (POST
                  /incidents/{id}/isolate). host_isolations.incident_id
                  es NOT NULL -- sin un incidente activo real para este
                  endpoint no hay a qué asociar la orden, así que el
                  botón queda deshabilitado con un motivo honesto en vez
                  de inventar un incidente. */}
              {!data.is_isolated && (
                <div className="px-5 py-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {isolateRequested ? (
                    <div
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold"
                      style={{ border: "1px solid var(--warn)", color: "var(--warn)", background: "var(--warn-soft)" }}
                    >
                      <i className={PENDING_ICON_CLASS} style={{ fontSize: "15px" }} />
                      {PENDING_LABEL_FULL}
                    </div>
                  ) : (
                    <button
                      disabled={!data.active_incident_id || isolating}
                      onClick={handleIsolate}
                      title={
                        data.active_incident_id
                          ? ISOLATE_TOOLTIP
                          : "No hay un incidente activo asociado a este endpoint -- el aislamiento se asocia siempre a un incidente real."
                      }
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 transition-premium btn-hover shadow-sm"
                      style={{ border: "1px solid var(--crit)", color: "var(--crit)", background: "var(--crit-soft)" }}
                    >
                      <i className={isolating ? SPINNER_ICON_CLASS : ISOLATE_ICON_CLASS} style={{ fontSize: "15px" }} />
                      {isolating ? SENDING_LABEL : ISOLATE_LABEL_FULL}
                    </button>
                  )}
                  {isolateError && (
                    <p className="text-[10.5px] mt-2 text-center" style={{ color: "var(--crit)" }}>{isolateError}</p>
                  )}
                  {!data.active_incident_id && !isolateRequested && (
                    <p className="text-[10.5px] mt-2 text-center" style={{ color: "var(--tx-mute)" }}>
                      No hay un incidente activo para este endpoint -- el aislamiento automático sí se ejecuta
                      cuando el motor heurístico determina que corresponde.
                    </p>
                  )}
                </div>
              )}

              {/* Acción de liberación -- mismo backend/máquina de estados
                  que "Liberar" en IsolationsHistoryTable.tsx y
                  CriticalIncidentsTable.tsx (POST /host-isolations/{id}/
                  release), una sola implementación en todo el sistema
                  (sección 13 de "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO
                  REAL...", 2026-08-17, ver PENDIENTES.md). Amarillo,
                  nunca rojo (sección 11) -- Liberar es lo opuesto de
                  Aislar, no una acción de riesgo. */}
              {data.is_isolated && (
                <div className="px-5 py-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
                  {releaseRequested ? (
                    <div
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold"
                      style={{ border: "1px solid var(--warn)", color: "var(--warn)", background: "var(--warn-soft)" }}
                    >
                      <i className="ph-fill ph-hourglass-medium" style={{ fontSize: "15px" }} />
                      Orden de liberación enviada -- esperando confirmación del agente
                    </div>
                  ) : (
                    <button
                      disabled={!data.isolation_id || releasing}
                      onClick={handleRelease}
                      title={data.isolation_id ? RELEASE_TOOLTIP : "No se encontró la orden de aislamiento asociada a este endpoint."}
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12.5px] font-semibold cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 transition-premium btn-hover shadow-sm"
                      style={{ border: "1px solid var(--warn)", color: "var(--warn)", background: "var(--warn-soft)" }}
                    >
                      <i className={releasing ? SPINNER_ICON_CLASS : RELEASE_ICON_CLASS} style={{ fontSize: "15px" }} />
                      {releasing ? SENDING_LABEL : RELEASE_LABEL_FULL}
                    </button>
                  )}
                  {releaseError && (
                    <p className="text-[10.5px] mt-2 text-center" style={{ color: "var(--crit)" }}>{releaseError}</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </aside>

      {rulesModalOpen && data && (
        <AgentRulesModal
          agentId={data.id}
          hostnameHint={data.hostname}
          onClose={() => setRulesModalOpen(false)}
        />
      )}
    </>
  );
}
