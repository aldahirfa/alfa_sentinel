// Puntaje de riesgo (0-100) con su barrita de progreso. Es el mismo
// componente en Alertas, Incidentes y el detalle de Respuesta, para que
// el puntaje se lea igual en todas las tablas. La columna se titula
// "Puntaje" para no confundirse con "Riesgo" de Endpoints, que es el
// nivel (Normal/Sospechoso/Alto/Crítico), no un número.

export default function RiskMeter({ score, color }: { score: number | null; color: string }) {
  if (score === null) return <span style={{ color: "var(--tx-mute)" }}>—</span>;
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="min-w-[92px]">
      <div className="flex items-baseline gap-1.5">
        <span className="text-[12px] font-bold tabular-nums" style={{ color }}>{score.toFixed(1)}</span>
        <span className="text-[8.5px]" style={{ color: "var(--tx-mute)" }}>/ 100</span>
      </div>
      <div className="h-[3px] rounded-full overflow-hidden mt-1.5" style={{ background: "var(--surf3)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
