import { useEffect, useState } from "react";
import AlertsSummaryCards from "../components/AlertsSummaryCards";
import AlertsFilters from "../components/AlertsFilters";
import AlertsTable from "../components/AlertsTable";
import AlertsPagination from "../components/AlertsPagination";
import AlertDrawer from "../components/AlertDrawer";
import { fetchAlerts } from "../api/client";
import type { AlertStatus, AlertsResponse } from "../types/alerts";
import type { Severity } from "../types/dashboard";
import { useRowFlash } from "../hooks/useRowFlash";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

const PAGE_SIZE = 15;
const DEBOUNCE_MS = 300;

interface Props {
  initialAlertSelection?: { id: number } | null;
  onViewIncident: (id: number) => void;
}

export default function AlertsPage({ initialAlertSelection = null, onViewIncident }: Props) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [status, setStatus] = useState<AlertStatus | "">("");
  const [since, setSince] = useState<"24h" | "7d" | "30d" | "">("");
  const [rule, setRule] = useState("");
  const [view, setView] = useState<"activas" | "todos">("activas");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const flashId = useRowFlash(selectedId);
  const { refreshToken } = useGlobalAlertsContext();

  useEffect(() => {
    if (initialAlertSelection != null) setSelectedId(initialAlertSelection.id);
  }, [initialAlertSelection]);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, severity, status, since, rule, view]);

  function load() {
    let cancelled = false;
    setLoading(true);
    fetchAlerts({ search, severity, status, since, rule, view, page, page_size: PAGE_SIZE })
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
    return () => { cancelled = true; };
  }

  useEffect(load, [search, severity, status, since, rule, view, page, refreshToken]);

  const hasFilters = Boolean(search || severity || status || since || rule);

  return (
    <main className="soc-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      {data && <AlertsSummaryCards summary={data.summary} />}

      <div className="px-1 pt-1">
        <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Investigación</div>
        <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>Priorización y análisis de detecciones</div>
        <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
          Filtra la cola por severidad, estado, período o mecanismo que originó la detección.
        </div>
      </div>

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
        view={view}
        onViewChange={setView}
        rules={data?.rules ?? []}
      />

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar la cola de alertas</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <>
          <AlertsTable
            alerts={data?.alerts ?? []}
            loading={loading}
            hasFilters={hasFilters}
            onSelect={setSelectedId}
            selectedId={selectedId}
            flashId={flashId}
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

      <AlertDrawer alertId={selectedId} onClose={() => setSelectedId(null)} onChanged={load} onViewIncident={onViewIncident} />
    </main>
  );
}
