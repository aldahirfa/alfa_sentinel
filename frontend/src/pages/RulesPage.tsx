import { useEffect, useState } from "react";
import RulesSummaryCards from "../components/RulesSummaryCards";
import RuleCard from "../components/RuleCard";
import { fetchRules } from "../api/client";
import type { HeuristicRule, RulesResponse } from "../types/rules";

export default function RulesPage() {
  const [data, setData] = useState<RulesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRules()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la lista de reglas heurísticas.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  function handleRuleChanged(updated: HeuristicRule) {
    setData((prev) => {
      if (!prev) return prev;
      const rules = prev.rules.map((r) => (r.id === updated.id ? updated : r));
      return {
        ...prev,
        rules,
        summary: {
          ...prev.summary,
          active: rules.filter((r) => r.is_active).length,
          inactive: rules.filter((r) => !r.is_active).length,
        },
      };
    });
  }

  return (
    <main className="soc-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      {data && <RulesSummaryCards summary={data.summary} />}

      <div className="px-1 pt-1">
        <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Lógica de detección</div>
        <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>Reglas y parámetros del motor heurístico</div>
        <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
          Consulta qué comportamiento evalúa cada regla, su umbral, ventana temporal, peso y actividad reciente.
        </div>
      </div>

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el motor heurístico</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : loading ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[250px] rounded-2xl animate-pulse" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
          {(data?.rules ?? []).map((rule) => (
            <RuleCard key={rule.id} rule={rule} onChanged={handleRuleChanged} />
          ))}
        </div>
      )}
    </main>
  );
}
