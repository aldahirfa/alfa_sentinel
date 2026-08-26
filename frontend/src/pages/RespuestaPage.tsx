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
          <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>
            Contención y recuperación
          </div>
          <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>
            Centro de acciones de respuesta
          </div>
          <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Ejecuta y supervisa aislamientos de red asociados a incidentes críticos, con trazabilidad de las acciones aplicadas sobre cada endpoint.
          </div>
        </div>
      </div>

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
          <CriticalIncidentsTable
            items={data?.critical_incidents ?? []}
            loading={loading}
            onIsolated={() => load(true)}
          />
          <IsolationsHistoryTable
            items={data?.isolations ?? []}
            loading={loading}
            onReleased={() => load(true)}
          />
        </>
      )}
    </main>
  );
}
