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
  // Mismo criterio que AlertsPage/IncidentesPage (2026-08-17, ver
  // PENDIENTES.md, sección 18/19): un cambio de estado de aislamiento
  // también debe reflejarse acá sin F5, usando la misma señal global.
  const { refreshToken } = useGlobalAlertsContext();

  // 'silent' evita el parpadeo de loading al refrescar después de una
  // acción (aislar/liberar) -- solo se usa el estado de carga completo
  // en el montaje inicial.
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
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {/* Mensaje honesto actualizado (2026-08-17, ver PENDIENTES.md,
          "Aislamiento de host -- modo development, laboratorio y
          producción"): el disparo MANUAL ya existe y usa el mismo
          mecanismo que el automático. La ejecución real vs. simulada
          depende de ALFA_SENTINEL_ENV (development=simulado,
          controlled_test/production=real). */}
      <div
        className="rounded-xl border p-5 flex items-start gap-3.5 shadow-sm"
        style={{ background: "var(--info-soft)", borderColor: "var(--info)" }}
      >
        <i className="ph-fill ph-info" style={{ fontSize: "20px", color: "var(--info)", marginTop: "2px" }} />
        <div className="text-[12.5px] leading-relaxed" style={{ color: "var(--tx)" }}>
          <strong>El aislamiento se ejecuta de verdad, automático o manual, con el mismo mecanismo.</strong>
          <br />
          El motor heurístico ordena aislar automáticamente cuando corresponde (honeyfile + actividad de
          archivos fuerte, o severidad crítica con múltiples indicadores); el botón "Aislar" de los
          incidentes críticos de abajo dispara la misma orden manualmente. En ambos casos el agente del
          endpoint la recibe, la ejecuta y confirma el resultado real ("Ejecutado" o "Falló la ejecución").
          En desarrollo (<code>ALFA_SENTINEL_ENV=development</code>) la ejecución queda simulada -- nunca
          toca el firewall real de esa máquina; en laboratorio (<code>controlled_test</code>) y producción
          es real.
        </div>
      </div>

      {error ? (
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      ) : (
        <>
          {data && <RespuestaSummaryCards summary={data.summary} />}
          <CriticalIncidentsTable items={data?.critical_incidents ?? []} loading={loading} onIsolated={() => load(true)} />
          <IsolationsHistoryTable items={data?.isolations ?? []} loading={loading} onReleased={() => load(true)} />
        </>
      )}
    </main>
  );
}
