import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import { fetchResponseEndpointDetail } from "../api/responseClient";
import type { ResponseEndpointDetail } from "../types/respuesta";
import { severityPillStyle } from "../lib/severity";
import { CONN_STATUS_LABEL } from "../lib/endpointStatus";

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

function osIcon(os: string): string {
  const value = os.toLowerCase();
  if (value.includes("win")) return "ph-fill ph-windows-logo";
  if (value.includes("linux") || value.includes("ubuntu") || value.includes("debian")) return "ph-fill ph-linux-logo";
  return "ph-fill ph-desktop";
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
        title="Detalle de respuesta"
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
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-4 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 0 ? "55%" : "100%" }} />)}
        </div>
      ) : (
        <>
          <section className="soc-panel rounded-2xl overflow-hidden">
            <div className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-4" style={{ background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                  <i className={osIcon(data.endpoint.operating_system)} style={{ fontSize: "18px" }} />
                </div>

                <div className="min-w-0">
                  <div className="text-[14px] font-semibold truncate" style={{ color: "var(--tx)" }}>{data.endpoint.hostname}</div>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>
                    <span>{data.endpoint.operating_system}{data.endpoint.os_version ? ` ${data.endpoint.os_version}` : ""}</span>
                    <span>·</span>
                    <span className="mono-data">{data.endpoint.ip_address}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-[9px]" style={{ color: "var(--tx-mute)" }}>
                    <span>Agente v{data.endpoint.agent_version ?? "—"}</span>
                    <span>·</span>
                    <span>{CONN_STATUS_LABEL[data.endpoint.agent_status === "ONLINE" ? "ONLINE" : "OFFLINE"]}</span>
                    <span>·</span>
                    <span>Última conexión: {data.endpoint.last_seen_at ?? "No disponible"}</span>
                  </div>
                </div>
              </div>

              <div className="md:ml-auto flex md:flex-col items-start md:items-end gap-2 md:gap-1.5 shrink-0">
                <div className="text-[8.5px] uppercase tracking-[.13em] font-bold" style={{ color: "var(--tx-mute)" }}>Estado de contención</div>
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[9.5px] font-bold whitespace-nowrap"
                  style={{ color: containment.color, background: containment.bg, border: `1px solid color-mix(in srgb, ${containment.color} 35%, transparent)` }}
                >
                  <i className={containment.icon} style={{ fontSize: "12px" }} />
                  {containment.label}
                </span>
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
                    <th className="px-3 py-3 font-semibold">Incidente asociado</th>
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
                        <td className="px-3 py-3.5 mono-data font-semibold" style={{ color: "var(--tx-dim)" }}>INC-{String(item.incident_id).padStart(5, "0")}</td>
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