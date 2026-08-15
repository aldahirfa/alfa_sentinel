import { useEffect, useState } from "react";
import IncidentesSummaryCards from "../components/IncidentesSummaryCards";
import IncidentesFilters from "../components/IncidentesFilters";
import IncidentesTable from "../components/IncidentesTable";
import IncidentesPagination from "../components/IncidentesPagination";
import IncidentDrawer from "../components/IncidentDrawer";
import { fetchIncidentes } from "../api/client";
import type { CombinedItem, IncidentesResponse, ItemKind, StatusBucket } from "../types/incidentes";
import type { Severity } from "../types/dashboard";

const DEBOUNCE_MS = 300;

export default function IncidentesPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusBucket | "">("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [since, setSince] = useState<"24h" | "7d" | "30d" | "">("");
  const [rule, setRule] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<IncidentesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ kind: ItemKind; id: number } | null>(null);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, status, severity, since, rule]);

  function load() {
    let cancelled = false;
    setLoading(true);
    fetchIncidentes({ search, status, severity, since, rule, page })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la lista de incidentes.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }

  useEffect(() => {
    return load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, severity, since, rule, page]);

  const hasFilters = Boolean(search || status || severity || since || rule);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {data && <IncidentesSummaryCards summary={data.summary} />}

      <IncidentesFilters
        search={searchInput}
        onSearchChange={setSearchInput}
        status={status}
        onStatusChange={setStatus}
        severity={severity}
        onSeverityChange={setSeverity}
        since={since}
        onSinceChange={setSince}
        rule={rule}
        onRuleChange={setRule}
        statusOptions={data?.filters.status_options ?? []}
        ruleOptions={data?.filters.rule_options ?? []}
      />

      {error ? (
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      ) : (
        <>
          <IncidentesTable
            items={data?.items ?? []}
            loading={loading}
            hasFilters={hasFilters}
            onSelect={(item: CombinedItem) => setSelected({ kind: item.kind, id: item.id })}
          />
          {data && (
            <IncidentesPagination
              page={data.page}
              pageSize={data.page_size}
              totalPages={data.total_pages}
              filteredTotal={data.filtered_total}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      <IncidentDrawer
        selected={selected}
        assignableUsers={data?.filters.assignable_users ?? []}
        onClose={() => setSelected(null)}
        onChanged={load}
      />
    </main>
  );
}
