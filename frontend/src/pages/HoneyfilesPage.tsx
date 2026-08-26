import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import HoneyfilesSummaryCards from "../components/HoneyfilesSummaryCards";
import HoneyfilesFilters from "../components/HoneyfilesFilters";
import HoneyfilesTable from "../components/HoneyfilesTable";
import HoneyfileDrawer from "../components/HoneyfileDrawer";
import DeployHoneyfileWizard from "../components/DeployHoneyfileWizard";
import { fetchHoneyfiles } from "../api/client";
import type { HoneyfileStatus, HoneyfilesResponse } from "../types/honeyfiles";
import { useRowFlash } from "../hooks/useRowFlash";

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
  const flashId = useRowFlash(selectedId);
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
    return () => { cancelled = true; };
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
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="honeyfiles"
        eyebrow="Tecnología de engaño"
        title="Cobertura y actividad de archivos señuelo"
        description="Gestiona los señuelos desplegados, su integridad y cualquier activación detectada en los endpoints."
      />

      {toast && (
        <div className="soc-panel rounded-2xl px-4 py-3 flex items-start gap-3" style={{ background: "var(--ok-soft)", borderColor: "color-mix(in srgb, var(--ok) 28%, var(--line-soft))" }}>
          <div className="w-8 h-8 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
            <i className="ph-fill ph-check-circle" style={{ fontSize: "16px" }} />
          </div>
          <div>
            <div className="text-[10.5px] font-semibold" style={{ color: "var(--ok)" }}>Despliegue procesado</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--tx-dim)" }}>{toast}</div>
          </div>
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
        <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
          <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
            <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
          </div>
          <div className="text-[12px] font-semibold">No se pudo cargar la cobertura de honeyfiles</div>
          <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
        </div>
      ) : (
        <HoneyfilesTable honeyfiles={data?.honeyfiles ?? []} loading={loading} hasFilters={hasFilters} onSelect={setSelectedId} selectedId={selectedId} flashId={flashId} />
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
