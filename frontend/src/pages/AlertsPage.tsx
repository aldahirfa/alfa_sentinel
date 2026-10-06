import { useEffect, useRef, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import AlertsSummaryCards from "../components/AlertsSummaryCards";
import AlertsFilters from "../components/AlertsFilters";
import AlertsTable from "../components/AlertsTable";
import AlertsPagination from "../components/AlertsPagination";
import AlertDrawer from "../components/AlertDrawer";
import { fetchAlerts } from "../api/client";
import type { AlertStatusFilter, AlertsResponse } from "../types/alerts";
import type { Severity } from "../types/dashboard";
import { useRowFlash } from "../hooks/useRowFlash";
import { useLiveRefresh } from "../hooks/useLiveRefresh";

const PAGE_SIZE = 15;
const DEBOUNCE_MS = 300;

interface Props {
  active: boolean;
  initialAlertSelection?: { id: number } | null;
  onViewIncident: (id: number) => void;
}

export default function AlertsPage({ active, initialAlertSelection = null, onViewIncident }: Props) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [status, setStatus] = useState<AlertStatusFilter | "">("");
  const [since, setSince] = useState<"24h" | "7d" | "30d" | "">("");
  const [rule, setRule] = useState("");
  const [view, setView] = useState<"activas" | "todos">("activas");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const flashId = useRowFlash(selectedId);
  const liveTick = useLiveRefresh(active);
  const requestSeq = useRef(0);

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

  // 'silent': recarga en segundo plano (useLiveRefresh), sin "cargando"
  // y sin reemplazar la tabla por un error si falla una vez. Solo se
  // aplica la respuesta del pedido más reciente.
  function load(silent = false) {
    const seq = ++requestSeq.current;
    if (!silent) setLoading(true);
    fetchAlerts({ search, severity, status, since, rule, view, page, page_size: PAGE_SIZE })
      .then((res) => {
        if (seq === requestSeq.current) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (seq === requestSeq.current && !silent) setError("No se pudo cargar la lista de alertas.");
      })
      .finally(() => {
        if (seq === requestSeq.current) setLoading(false);
      });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(), [search, severity, status, since, rule, view, page]);

  useEffect(() => {
    if (liveTick) load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveTick]);

  const hasFilters = Boolean(search || severity || status || since || rule);

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="alerts"
        eyebrow="Investigación"
        title="Priorización y análisis de detecciones"
        description="Filtra la cola por severidad, estado, período o mecanismo que originó la detección."
      />

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
          <AlertsTable alerts={data?.alerts ?? []} loading={loading} hasFilters={hasFilters} onSelect={setSelectedId} selectedId={selectedId} flashId={flashId} />
          {data && <AlertsPagination page={data.page} pageSize={data.page_size} totalPages={data.total_pages} filteredTotal={data.filtered_total} onPageChange={setPage} />}
        </>
      )}

      <AlertDrawer alertId={selectedId} refreshKey={liveTick} onClose={() => setSelectedId(null)} onChanged={() => load(true)} onViewIncident={onViewIncident} />
    </main>
  );
}
