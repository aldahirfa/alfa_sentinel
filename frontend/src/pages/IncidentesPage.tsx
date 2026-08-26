import { useEffect, useState } from "react";
import IncidentesSummaryCards from "../components/IncidentesSummaryCards";
import IncidentesFilters from "../components/IncidentesFilters";
import IncidentesTable from "../components/IncidentesTable";
import IncidentesPagination from "../components/IncidentesPagination";
import IncidentDrawer from "../components/IncidentDrawer";
import { fetchIncidentes } from "../api/client";
import type { CombinedItem, IncidentesResponse, ItemKind, StatusBucket } from "../types/incidentes";
import type { Severity } from "../types/dashboard";
import { useRowFlash } from "../hooks/useRowFlash";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

const DEBOUNCE_MS = 300;

interface Props {
  initialSelection?: { kind: ItemKind; id: number } | null;
  onViewAlert: (id: number) => void;
}

export default function IncidentesPage({ initialSelection = null, onViewAlert }: Props) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusBucket | "">("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [since, setSince] = useState<"24h" | "7d" | "30d" | "">("");
  const [rule, setRule] = useState("");
  const [view, setView] = useState<"activas" | "todos">("activas");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<IncidentesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ kind: ItemKind; id: number } | null>(null);
  const selectedKey = selected ? `${selected.kind}:${selected.id}` : null;
  const flashKey = useRowFlash(selectedKey);
  const { refreshToken } = useGlobalAlertsContext();

  useEffect(() => {
    if (initialSelection != null) setSelected(initialSelection);
  }, [initialSelection]);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, status, severity, since, rule, view]);

  function load() {
    let cancelled = false;
    setLoading(true);
    fetchIncidentes({ search, status, severity, since, rule, view, page })
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
    return () => { cancelled = true; };
  }

  useEffect(() => {
    return load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, severity, since, rule, view, page, refreshToken]);

  const hasFilters = Boolean(search || status || severity || since || rule);

  return (
    <main className="soc-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      {data && <IncidentesSummaryCards summary={data.summary} />}

      <div className="px-1 pt-1">
        <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Investigación y respuesta</div>
        <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>Gestión centralizada de casos</div>
        <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
          Prioriza incidentes, asigna responsables y ejecuta acciones de contención sobre los endpoints afectados.
        </div>
      </div>

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
        view={view}
        onViewChange={setView}
        statusOptions={data?.filters.status_options ?? []}
        ruleOptions={data?.filters.rule_options ?? []}
      />

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el centro de incidentes</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <>
          <IncidentesTable
            items={data?.items ?? []}
            loading={loading}
            hasFilters={hasFilters}
            onSelect={(item: CombinedItem) => setSelected({ kind: item.kind, id: item.id })}
            onIsolated={load}
            selectedKey={selectedKey}
            flashKey={flashKey}
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
        onViewAlert={onViewAlert}
      />
    </main>
  );
}
