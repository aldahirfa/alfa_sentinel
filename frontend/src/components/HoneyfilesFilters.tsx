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
    ? { background: "var(--brand-soft)", color: "var(--brand)" }
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
    <section
      className="rounded-[10px] border p-3.5 flex flex-col gap-3"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="flex gap-2">
        <div className="relative flex-1">
          <i
            className="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2"
            style={{ fontSize: "15px", color: "var(--tx-mute)" }}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar por nombre de archivo, ruta local o hostname..."
            className="w-full pl-9 pr-3 py-2 rounded-[9px] text-[13px] outline-none"
            style={{
              background: "var(--surf2)",
              border: "1.5px solid var(--line)",
              color: "var(--tx)",
            }}
          />
        </div>
        <button
          onClick={onDeployClick}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-[9px] text-[12.5px] font-semibold border-0 cursor-pointer whitespace-nowrap"
          style={{ background: "var(--brand)", color: "#fff" }}
        >
          <i className="ph ph-plus" style={{ fontSize: "14px" }} />
          Desplegar honeyfile
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Estado</span>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt || "all"}
                onClick={() => onStatusChange(opt)}
                className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
                style={segStyle(status === opt)}
              >
                {opt ? HONEYFILE_STATUS_LABEL[opt] : "Todos"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Sistema operativo</span>
          <select
            value={os}
            onChange={(e) => onOsChange(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {distinctOs.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
