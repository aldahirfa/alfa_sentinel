import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import EndpointsSummaryCards from "../components/EndpointsSummaryCards";
import EndpointsFilters from "../components/EndpointsFilters";
import EndpointsTable from "../components/EndpointsTable";
import EndpointsPagination from "../components/EndpointsPagination";
import EndpointDrawer from "../components/EndpointDrawer";
import { fetchEndpoints } from "../api/client";
import type { ConnStatus, EndpointsResponse } from "../types/endpoints";
import type { Severity } from "../types/dashboard";
import { useRowFlash } from "../hooks/useRowFlash";

const PAGE_SIZE = 10;
const DEBOUNCE_MS = 300;

export default function EndpointsPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ConnStatus | "">("");
  const [risk, setRisk] = useState<Severity | "">("");
  const [osFamily, setOsFamily] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EndpointsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const flashId = useRowFlash(selectedId);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, status, risk, osFamily]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchEndpoints({ search, status, risk, os_family: osFamily, page, page_size: PAGE_SIZE })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la lista de endpoints.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [search, status, risk, osFamily, page]);

  const hasFilters = Boolean(search || status || risk || osFamily);

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="endpoints"
        eyebrow="Superficie de protección"
        title="Inventario y estado de los agentes"
        description="Consulta conectividad, riesgo, salud del agente, actividad y alertas asociadas a cada equipo monitoreado."
      />

      {data && <EndpointsSummaryCards summary={data.summary} />}

      <EndpointsFilters
        search={searchInput}
        onSearchChange={setSearchInput}
        status={status}
        onStatusChange={setStatus}
        risk={risk}
        onRiskChange={setRisk}
        osFamily={osFamily}
        onOsFamilyChange={setOsFamily}
        osFamilies={data?.os_families ?? []}
      />

      {error ? (
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar el inventario de endpoints</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <>
          <EndpointsTable endpoints={data?.endpoints ?? []} loading={loading} hasFilters={hasFilters} onSelect={setSelectedId} selectedId={selectedId} flashId={flashId} />
          {data && <EndpointsPagination page={data.page} pageSize={data.page_size} totalPages={data.total_pages} filteredTotal={data.filtered_total} onPageChange={setPage} />}
        </>
      )}

      <EndpointDrawer endpointId={selectedId} onClose={() => setSelectedId(null)} />
    </main>
  );
}
