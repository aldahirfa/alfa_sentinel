import { useEffect, useState } from "react";
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

  // Debounce del buscador -- no dispara un pedido por cada tecla.
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  // Cualquier cambio de filtro vuelve a la página 1.
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
    return () => {
      cancelled = true;
    };
  }, [search, status, risk, osFamily, page]);

  const hasFilters = Boolean(search || status || risk || osFamily);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
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
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      ) : (
        <>
          <EndpointsTable
            endpoints={data?.endpoints ?? []}
            loading={loading}
            hasFilters={hasFilters}
            onSelect={setSelectedId}
            selectedId={selectedId}
            flashId={flashId}
          />
          {data && (
            <EndpointsPagination
              page={data.page}
              pageSize={data.page_size}
              totalPages={data.total_pages}
              filteredTotal={data.filtered_total}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      <EndpointDrawer endpointId={selectedId} onClose={() => setSelectedId(null)} />
    </main>
  );
}
