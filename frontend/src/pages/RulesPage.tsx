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
    return () => {
      cancelled = true;
    };
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
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {data && <RulesSummaryCards summary={data.summary} />}

      {error ? (
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      ) : loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[130px] rounded-[10px] animate-pulse" style={{ background: "var(--surf2)" }} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {(data?.rules ?? []).map((rule) => (
            <RuleCard key={rule.id} rule={rule} onChanged={handleRuleChanged} />
          ))}
        </div>
      )}
    </main>
  );
}
