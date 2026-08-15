import { useEffect, useState } from "react";
import AlertsSummaryCards from "../components/AlertsSummaryCards";
import AlertsFilters from "../components/AlertsFilters";
import AlertsTable from "../components/AlertsTable";
import AlertsPagination from "../components/AlertsPagination";
import AlertDrawer from "../components/AlertDrawer";
import { fetchAlerts } from "../api/client";
import type { AlertStatus, AlertsResponse } from "../types/alerts";
import type { Severity } from "../types/dashboard";

const PAGE_SIZE = 15;
const DEBOUNCE_MS = 300;

export default function AlertsPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [status, setStatus] = useState<AlertStatus | "">("");
  const [since, setSince] = useState<"24h" | "7d" | "30d" | "">("");
  const [rule, setRule] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Debounce del buscador -- no dispara un pedido por cada tecla.
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  // Cualquier cambio de filtro vuelve a la página 1.
  useEffect(() => {
    setPage(1);
  }, [search, severity, status, since, rule]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchAlerts({ search, severity, status, since, rule, page, page_size: PAGE_SIZE })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la lista de alertas.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, severity, status, since, rule, page]);

  const hasFilters = Boolean(search || severity || status || since || rule);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {data && <AlertsSummaryCards summary={data.summary} />}

      <AlertsFilters
        search={searchInput}
        onSearchChange={setSearchInput}
        severity={severity}
        onSeverityChange={setSeverity}
        status={status}
        onStatusChange={setStatus}
        since={since}
        onSinceChange={setSince}
        rule={rule}
        onRuleChange={setRule}
        rules={data?.rules ?? []}
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
          <AlertsTable
            alerts={data?.alerts ?? []}
            loading={loading}
            hasFilters={hasFilters}
            onSelect={setSelectedId}
          />
          {data && (
            <AlertsPagination
              page={data.page}
              pageSize={data.page_size}
              totalPages={data.total_pages}
              filteredTotal={data.filtered_total}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      <AlertDrawer alertId={selectedId} onClose={() => setSelectedId(null)} />
    </main>
  );
}
