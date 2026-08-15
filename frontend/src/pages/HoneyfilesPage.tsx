import { useEffect, useState } from "react";
import HoneyfilesSummaryCards from "../components/HoneyfilesSummaryCards";
import HoneyfilesFilters from "../components/HoneyfilesFilters";
import HoneyfilesTable from "../components/HoneyfilesTable";
import HoneyfileDrawer from "../components/HoneyfileDrawer";
import DeployHoneyfileWizard from "../components/DeployHoneyfileWizard";
import { fetchHoneyfiles } from "../api/client";
import type { HoneyfileStatus, HoneyfilesResponse } from "../types/honeyfiles";

const DEBOUNCE_MS = 300;

export default function HoneyfilesPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<HoneyfileStatus | "">("");
  const [os, setOs] = useState("");

  const [data, setData] = useState<HoneyfilesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  function load() {
    let cancelled = false;
    setLoading(true);
    fetchHoneyfiles({ search, status, os })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar la lista de honeyfiles.");
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
  }, [search, status, os]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  const hasFilters = Boolean(search || status || os);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      {toast && (
        <div
          className="rounded-[10px] border px-4 py-3 text-[12.5px] flex items-start gap-2"
          style={{ background: "var(--ok-soft)", borderColor: "var(--ok)", color: "var(--ok)" }}
        >
          <i className="ph-fill ph-check-circle" style={{ fontSize: "16px", marginTop: "1px" }} />
          {toast}
        </div>
      )}

      {data && <HoneyfilesSummaryCards summary={data.summary} />}

      <HoneyfilesFilters
        search={searchInput}
        onSearchChange={setSearchInput}
        status={status}
        onStatusChange={setStatus}
        os={os}
        onOsChange={setOs}
        distinctOs={data?.distinct_os ?? []}
        onDeployClick={() => setWizardOpen(true)}
      />

      {error ? (
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      ) : (
        <HoneyfilesTable
          honeyfiles={data?.honeyfiles ?? []}
          loading={loading}
          hasFilters={hasFilters}
          onSelect={setSelectedId}
        />
      )}

      <HoneyfileDrawer honeyfileId={selectedId} onClose={() => setSelectedId(null)} onChanged={load} />

      <DeployHoneyfileWizard
        open={wizardOpen}
        availableAgents={data?.available_agents ?? []}
        onClose={() => setWizardOpen(false)}
        onDeployed={(message) => {
          setToast(message);
          load();
        }}
      />
    </main>
  );
}
