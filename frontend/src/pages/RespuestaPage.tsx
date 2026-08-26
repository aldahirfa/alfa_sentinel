import { useEffect, useState } from "react";
import RespuestaSummaryCards from "../components/RespuestaSummaryCards";
import CriticalIncidentsTable from "../components/CriticalIncidentsTable";
import IsolationsHistoryTable from "../components/IsolationsHistoryTable";
import { fetchRespuesta } from "../api/client";
import type { RespuestaResponse } from "../types/respuesta";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

export default function RespuestaPage() {
  const [data, setData] = useState<RespuestaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEnvironmentInfo, setShowEnvironmentInfo] = useState(false);
  const { refreshToken } = useGlobalAlertsContext();

  function load(silent = false) {
    if (!silent) setLoading(true);
    return fetchRespuesta()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch(() => {
        setError("No se pudo cargar la información de respuesta.");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  return (
    <main className="soc-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      {data && <RespuestaSummaryCards summary={data.summary} />}

      <div className="flex items-end justify-between gap-4 flex-wrap px-1 pt-1">
        <div>
          <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Contención y recuperación</div>
          <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>Centro de acciones de respuesta</div>
          <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Ejecuta y supervisa aislamientos de red asociados a incidentes críticos, con trazabilidad completa de cada acción.
          </div>
        </div>
        <div className="flex items-center gap-2 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--ok)", boxShadow: "0 0 0 3px var(--ok-soft)" }} />
          Canal de respuesta disponible
        </div>
      </div>

      <section className="soc-panel rounded-2xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowEnvironmentInfo((v) => !v)}
          className="w-full px-4 py-3.5 flex items-center gap-3 text-left border-0 cursor-pointer transition-premium"
          style={{ background: "linear-gradient(90deg, var(--info-fill), var(--surf))", color: "var(--tx)" }}
        >
          <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
            <i className="ph ph-info" style={{ fontSize: "17px" }} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[10.5px] font-semibold">Modo de ejecución del aislamiento</div>
            <div className="text-[9.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
              La misma orden se usa para contención automática y manual; el efecto real depende del entorno configurado.
            </div>
          </div>
          <span className="text-[9.5px] font-semibold flex items-center gap-1.5" style={{ color: "var(--brand)" }}>
            {showEnvironmentInfo ? "Ocultar detalles" : "Ver detalles"}
            <i className={showEnvironmentInfo ? "ph ph-caret-up" : "ph ph-caret-down"} />
          </span>
        </button>

        {showEnvironmentInfo && (
          <div className="px-4 pb-4 pt-1 border-t" style={{ borderColor: "var(--line-soft)" }}>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mt-3">
              <div className="rounded-xl border p-3" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
                <div className="text-[9px] font-bold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Development</div>
                <div className="text-[10.5px] font-semibold mt-1.5" style={{ color: "var(--warn)" }}>Ejecución simulada</div>
                <div className="text-[9.5px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>No modifica el firewall real del endpoint.</div>
              </div>
              <div className="rounded-xl border p-3" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
                <div className="text-[9px] font-bold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Controlled test</div>
                <div className="text-[10.5px] font-semibold mt-1.5" style={{ color: "var(--info)" }}>Ejecución real controlada</div>
                <div className="text-[9.5px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>El agente aplica la orden en el entorno de laboratorio.</div>
              </div>
              <div className="rounded-xl border p-3" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
                <div className="text-[9px] font-bold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Production</div>
                <div className="text-[10.5px] font-semibold mt-1.5" style={{ color: "var(--crit)" }}>Ejecución real</div>
                <div className="text-[9.5px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>La contención modifica efectivamente la conectividad del host.</div>
              </div>
            </div>
          </div>
        )}
      </section>

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el centro de respuesta</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <>
          <CriticalIncidentsTable items={data?.critical_incidents ?? []} loading={loading} onIsolated={() => load(true)} />
          <IsolationsHistoryTable items={data?.isolations ?? []} loading={loading} onReleased={() => load(true)} />
        </>
      )}
    </main>
  );
}
