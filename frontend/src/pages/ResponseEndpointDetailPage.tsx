import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import { fetchResponseEndpointDetail } from "../api/responseClient";
import type { ResponseEndpointDetail } from "../types/respuesta";
import { severityPillStyle } from "../lib/severity";

interface Props {
  agentId: number;
  onBack: () => void;
  onViewIncident: (id: number) => void;
}

function containmentStyle(status: string | null) {
  if (status === "EXECUTED") return { label: "Aislado", color: "var(--crit)", bg: "var(--crit-soft)", icon: "ph-fill ph-plugs" };
  if (status === "REQUESTED") return { label: "Aislamiento pendiente", color: "var(--warn)", bg: "var(--warn-soft)", icon: "ph-fill ph-hourglass-medium" };
  if (status === "RELEASE_REQUESTED") return { label: "Liberación pendiente", color: "var(--warn)", bg: "var(--warn-soft)", icon: "ph-fill ph-hourglass-medium" };
  if (status === "ISOLATION_FAILED") return { label: "Aislamiento fallido", color: "var(--crit)", bg: "var(--crit-soft)", icon: "ph-fill ph-warning-circle" };
  return { label: "No aislado", color: "var(--ok)", bg: "var(--ok-soft)", icon: "ph-fill ph-check-circle" };
}

function isolationTone(status: string) {
  if (status === "EXECUTED") return { color: "var(--crit)", bg: "var(--crit-soft)" };
  if (status === "REQUESTED" || status === "RELEASE_REQUESTED") return { color: "var(--warn)", bg: "var(--warn-soft)" };
  if (status === "ISOLATION_FAILED") return { color: "var(--crit)", bg: "var(--crit-soft)" };
  return { color: "var(--tx-dim)", bg: "var(--surf3)" };
}

export default function ResponseEndpointDetailPage({ agentId, onBack, onViewIncident }: Props) {
  const [data, setData] = useState<ResponseEndpointDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchResponseEndpointDetail(agentId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "No se pudo cargar el detalle del endpoint."))
      .finally(() => setLoading(false));
  }, [agentId]);

  const containment = containmentStyle(data?.endpoint.isolation_status ?? null);

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <div>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover"
          style={{ color: "var(--tx-dim)", background: "var(--surf2)", borderColor: "var(--line)" }}
        >
          <i className="ph ph-arrow-left" />
          <span className="text-[11px] font-semibold">Volver a acciones de respuesta</span>
        </button>
      </div>

      <ModuleIntro
        page="respuesta"
        eyebrow="Trazabilidad por endpoint"
        title={data?.endpoint.hostname ?? "Detalle de contención"}
        description="Consulta los incidentes y el historial de aislamiento asociados a este endpoint sin mezclar registros de otros equipos."
      />

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el detalle de contención</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : loading || !data ? (
        <div className="soc-panel rounded-2xl p-6 flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-4 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 0 ? "55%" : "100%" }} />)}
        </div>
      ) : (
        <>
          <section className="soc-panel-strong rounded-[20px] p-5 relative overflow-hidden">
            <div className="absolute -right-14 -top-16 w-56 h-56 rounded-full pointer-events-none" style={{ background: containment.bg, filter: "blur(38px)", opacity: .38 }} />
            <div className="relative z-[1] grid grid-cols-1 xl:grid-cols-[1.2fr_.8fr] gap-5">
              <div>
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-2xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                    <i className="ph ph-desktop-tower" style={{ fontSize: "19px" }} />
                  </div>
                  <div>
                    <div className="text-[16px] font-bold" style={{ color: "var(--tx)" }}>{data.endpoint.hostname}</div>
                    <div className="mono-data text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{data.endpoint.ip_address}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
                  <div className="rounded-xl px-3 py-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                    <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Sistema operativo</div>
                    <div className="text-[11px] font-semibold mt-1.5" style={{ color: "var(--tx)" }}>{data.endpoint.operating_system}</div>
                    <div className="text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{data.endpoint.os_version || "—"}</div>
                  </div>
                  <div className="rounded-xl px-3 py-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                    <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Agente</div>
                    <div className="text-[11px] font-semibold mt-1.5" style={{ color: data.endpoint.agent_status === "ONLINE" ? "var(--ok)" : "var(--tx-dim)" }}>{data.endpoint.agent_status === "ONLINE" ? "Activo" : "Sin conexión"}</div>
                    <div className="text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>v{data.endpoint.agent_version ?? "—"}</div>
                  </div>
                  <div className="rounded-xl px-3 py-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                    <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Incidentes</div>
                    <div className="text-[20px] font-bold mt-1 tabular-nums" style={{ color: "var(--tx)" }}>{data.summary.incidents_total}</div>
                  </div>
                  <div className="rounded-xl px-3 py-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
                    <div className="text-[8.5px] uppercase tracking-[.1em] font-bold" style={{ color: "var(--tx-mute)" }}>Acciones registradas</div>
                    <div className="text-[20px] font-bold mt-1 tabular-nums" style={{ color: "var(--tx)" }}>{data.summary.isolations_total}</div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border p-4 flex flex-col justify-center" style={{ background: containment.bg, borderColor: containment.color }}>
                <div className="text-[9px] uppercase tracking-[.14em] font-bold" style={{ color: "var(--tx-mute)" }}>Estado actual de contención</div>
                <div className="flex items-center gap-2 mt-3 text-[17px] font-bold" style={{ color: containment.color }}>
                  <i className={containment.icon} />
                  {containment.label}
                </div>
                <div className="text-[10px] mt-3 leading-relaxed" style={{ color: "var(--tx-dim)" }}>
                  Último heartbeat: {data.endpoint.last_seen_at ?? "No disponible"}
                </div>
              </div>
            </div>
          </section>

          <section className="soc-panel rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
              <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                <i className="ph-fill ph-siren" style={{ fontSize: "16px" }} />
              </div>
              <div>
                <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Casos relacionados</div>
                <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Incidentes asociados al endpoint</div>
              </div>
              <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{data.incidents.length} registros</div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[11px] min-w-[980px]">
                <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
                  <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
                    <th className="px-4 py-3 font-semibold">Incidente</th>
                    <th className="px-3 py-3 font-semibold">Severidad</th>
                    <th className="px-3 py-3 font-semibold">Riesgo</th>
                    <th className="px-3 py-3 font-semibold">Estado</th>
                    <th className="px-3 py-3 font-semibold">Responsable</th>
                    <th className="px-3 py-3 font-semibold">Apertura</th>
                    <th className="px-4 py-3 font-semibold text-right">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {data.incidents.length === 0 ? (
                    <tr><td colSpan={7} className="py-12 text-center" style={{ color: "var(--tx-mute)" }}>Este endpoint todavía no tiene incidentes asociados.</td></tr>
                  ) : data.incidents.map((incident) => (
                    <tr key={incident.id} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                      <td className="px-4 py-3.5">
                        <div className="font-bold" style={{ color: "var(--tx)" }}>{incident.code}</div>
                        <div className="text-[9px] mt-1 truncate max-w-[280px]" style={{ color: "var(--tx-mute)" }}>{incident.title}</div>
                      </td>
                      <td className="px-3 py-3.5">{incident.severity ? <span className="text-[9px] font-bold px-2 py-1 rounded-md" style={severityPillStyle(incident.severity)}>{incident.severity.toUpperCase()}</span> : "—"}</td>
                      <td className="px-3 py-3.5 font-bold tabular-nums" style={{ color: "var(--tx-dim)" }}>{incident.risk_score.toFixed(1)}</td>
                      <td className="px-3 py-3.5"><span className="text-[9.5px] font-semibold" style={{ color: incident.status === "CLOSED" ? "var(--ok)" : "var(--warn)" }}>{incident.status_label}</span></td>
                      <td className="px-3 py-3.5" style={{ color: incident.assigned_to_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>{incident.assigned_to_name ?? "Sin asignar"}</td>
                      <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{incident.opened_at ?? "—"}</td>
                      <td className="px-4 py-3.5 text-right">
                        <button onClick={() => onViewIncident(incident.id)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover" style={{ color: "var(--brand)", background: "var(--brand-fill)", borderColor: "var(--brand-soft)" }}>
                          <span className="text-[10px] font-semibold">Ver incidente</span><i className="ph ph-arrow-right" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="soc-panel rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
              <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                <i className="ph ph-clock-counter-clockwise" style={{ fontSize: "17px" }} />
              </div>
              <div>
                <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Trazabilidad</div>
                <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Historial de aislamiento y liberación</div>
              </div>
              <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{data.isolations.length} registros</div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[11px] min-w-[980px]">
                <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
                  <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
                    <th className="px-4 py-3 font-semibold">Estado</th>
                    <th className="px-3 py-3 font-semibold">Solicitado</th>
                    <th className="px-3 py-3 font-semibold">Solicitado por</th>
                    <th className="px-3 py-3 font-semibold">Ejecutado</th>
                    <th className="px-3 py-3 font-semibold">Liberado</th>
                    <th className="px-3 py-3 font-semibold">Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.isolations.length === 0 ? (
                    <tr><td colSpan={6} className="py-12 text-center" style={{ color: "var(--tx-mute)" }}>Este endpoint todavía no tiene acciones de contención registradas.</td></tr>
                  ) : data.isolations.map((item) => {
                    const tone = isolationTone(item.status);
                    return (
                      <tr key={item.id} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                        <td className="px-4 py-3.5"><span className="inline-flex px-2.5 py-1.5 rounded-lg text-[9.5px] font-bold" style={{ color: tone.color, background: tone.bg }}>{item.status_label}</span></td>
                        <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.requested_at ?? "—"}</td>
                        <td className="px-3 py-3.5" style={{ color: item.requested_by_name ? "var(--tx-dim)" : "var(--tx-mute)" }}>{item.requested_by_name ?? "Automático (motor heurístico)"}</td>
                        <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.executed_at ?? "—"}</td>
                        <td className="px-3 py-3.5 tabular-nums" style={{ color: "var(--tx-mute)" }}>{item.released_at ?? "—"}</td>
                        <td className="px-3 py-3.5 max-w-[360px]" style={{ color: "var(--tx-mute)" }} title={item.result ?? undefined}>{item.result ?? item.reason ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
