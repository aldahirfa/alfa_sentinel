import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import RespuestaSummaryCards from "../components/RespuestaSummaryCards";
import ResponseEndpointsTable from "../components/ResponseEndpointsTable";
import ResponseEndpointDetailPage from "./ResponseEndpointDetailPage";
import { fetchResponseEndpoints } from "../api/responseClient";
import type { ResponseEndpointsResponse } from "../types/respuesta";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

interface Props {
  endpointId: number | null;
  onOpenEndpoint: (agentId: number) => void;
  onBack: () => void;
  onViewIncident: (id: number) => void;
}

export default function RespuestaPage({ endpointId, onOpenEndpoint, onBack, onViewIncident }: Props) {
  const [data, setData] = useState<ResponseEndpointsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { refreshToken } = useGlobalAlertsContext();

  function load(silent = false) {
    if (!silent) setLoading(true);
    return fetchResponseEndpoints()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "No se pudo cargar la información de respuesta."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (endpointId === null) load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken, endpointId]);

  if (endpointId !== null) {
    return <ResponseEndpointDetailPage agentId={endpointId} onBack={onBack} onViewIncident={onViewIncident} />;
  }

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="respuesta"
        eyebrow="Contención operativa"
        title="Acciones de respuesta por endpoint"
        description="Administra aislamiento y liberación sobre los endpoints registrados. Cada equipo aparece una sola vez; su historial e incidentes asociados se consultan desde Ver detalles."
      />

      {data && <RespuestaSummaryCards summary={data.summary} />}

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el centro de respuesta</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <ResponseEndpointsTable
          items={data?.endpoints ?? []}
          loading={loading}
          onChanged={() => load(true)}
          onOpenDetail={onOpenEndpoint}
        />
      )}
    </main>
  );
}
