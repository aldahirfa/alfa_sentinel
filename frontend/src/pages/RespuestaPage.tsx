import { useEffect, useState } from "react";
import RespuestaSummaryCards from "../components/RespuestaSummaryCards";
import CriticalIncidentsTable from "../components/CriticalIncidentsTable";
import IsolationsHistoryTable from "../components/IsolationsHistoryTable";
import { fetchRespuesta } from "../api/client";
import type { RespuestaResponse } from "../types/respuesta";

export default function RespuestaPage() {
  const [data, setData] = useState<RespuestaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRespuesta()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la información de respuesta.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {/* Mismo mensaje honesto que el placeholder real de /respuesta --
          no se simula un botón de aislamiento que funcione. */}
      <div
        className="rounded-[10px] border px-4 py-3.5 flex items-start gap-3"
        style={{ background: "var(--info-soft)", borderColor: "var(--info)" }}
      >
        <i className="ph ph-info" style={{ fontSize: "18px", color: "var(--info)", marginTop: "1px" }} />
        <div className="text-[12.5px] leading-relaxed" style={{ color: "var(--tx)" }}>
          <strong>El aislamiento de endpoints es parte del diseño del sistema, pero la respuesta automática todavía no está implementada.</strong>
          <br />
          El agente no tiene un canal para recibir ni ejecutar comandos remotos, así que por ahora la contención ante una detección crítica es manual, fuera de esta consola. La tabla de abajo muestra qué incidentes la necesitarían ahora mismo.
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
          <CriticalIncidentsTable items={data?.critical_incidents ?? []} loading={loading} />
          <IsolationsHistoryTable items={data?.isolations ?? []} loading={loading} />
        </>
      )}
    </main>
  );
}
