import type { HoneyfileStatus } from "../types/honeyfiles";
import { HONEYFILE_STATUS_LABEL } from "../lib/honeyfileStatus";

interface Props {
  search: string;
  onSearchChange: (v: string) => void;
  status: HoneyfileStatus | "";
  onStatusChange: (v: HoneyfileStatus | "") => void;
  os: string;
  onOsChange: (v: string) => void;
  distinctOs: string[];
  onDeployClick: () => void;
}

const STATUS_OPTIONS: (HoneyfileStatus | "")[] = ["", "ACTIVE", "TRIGGERED", "INACTIVE"];

function segStyle(active: boolean): React.CSSProperties {
  return active
    ? { background: "var(--brand)", color: "#fff", boxShadow: "0 5px 16px var(--brand-glow)" }
    : { background: "transparent", color: "var(--tx-mute)" };
}

export default function HoneyfilesFilters({
  search,
  onSearchChange,
  status,
  onStatusChange,
  os,
  onOsChange,
  distinctOs,
  onDeployClick,
}: Props) {
  return (
    <section className="soc-panel rounded-2xl p-4 flex flex-col gap-3.5">
      <div className="flex flex-col lg:flex-row gap-3">
        <div className="relative flex-1">
          <i className="ph ph-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2" style={{ fontSize: "15px", color: "var(--tx-mute)" }} />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar honeyfile, ruta o endpoint..."
            className="w-full pl-10 pr-3 py-2.5 rounded-xl text-[12px] outline-none transition-premium"
            style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx)" }}
          />
        </div>
        <button
          onClick={onDeployClick}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-[11px] font-semibold border cursor-pointer whitespace-nowrap transition-premium btn-hover"
          style={{ background: "var(--brand)", borderColor: "var(--brand)", color: "#fff", boxShadow: "0 8px 22px var(--brand-glow)" }}
        >
          <i className="ph ph-file-plus" style={{ fontSize: "14px" }} />
          Desplegar honeyfile
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-0.5">
        <div className="flex items-center gap-2">
          <span className="text-[9.5px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Estado</span>
          <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt || "all"}
                onClick={() => onStatusChange(opt)}
                className="px-3 py-1.5 rounded-lg text-[10px] font-semibold border-0 cursor-pointer transition-premium"
                style={segStyle(status === opt)}
              >
                {opt ? HONEYFILE_STATUS_LABEL[opt] : "Todos"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <span className="text-[9.5px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Sistema operativo</span>
          <select
            value={os}
            onChange={(e) => onOsChange(e.target.value)}
            className="px-3 py-2 rounded-xl text-[10.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {distinctOs.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      </div>
    </section>
  );
}
