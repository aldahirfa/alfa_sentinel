import type { ConnStatus } from "../types/endpoints";
import type { Severity } from "../types/dashboard";
import { CONN_STATUS_LABEL } from "../lib/endpointStatus";
import { SEVERITY_LABEL } from "../lib/severity";

interface Props {
  search: string;
  onSearchChange: (v: string) => void;
  status: ConnStatus | "";
  onStatusChange: (v: ConnStatus | "") => void;
  risk: Severity | "";
  onRiskChange: (v: Severity | "") => void;
  osFamily: string;
  onOsFamilyChange: (v: string) => void;
  osFamilies: string[];
}

const STATUS_OPTIONS: (ConnStatus | "")[] = ["", "ONLINE", "OFFLINE", "ISOLATED"];
const RISK_OPTIONS: (Severity | "")[] = ["", "NORMAL", "SUSPICIOUS", "HIGH", "CRITICAL"];

function segStyle(active: boolean): React.CSSProperties {
  return active
    ? { background: "var(--brand-soft)", color: "var(--brand)" }
    : { background: "transparent", color: "var(--tx-mute)" };
}

export default function EndpointsFilters({
  search,
  onSearchChange,
  status,
  onStatusChange,
  risk,
  onRiskChange,
  osFamily,
  onOsFamilyChange,
  osFamilies,
}: Props) {
  return (
    <section
      className="rounded-[10px] border p-3.5 flex flex-col gap-3"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="relative">
        <i
          className="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2"
          style={{ fontSize: "15px", color: "var(--tx-mute)" }}
        />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Buscar endpoint, hostname o dirección IP..."
          className="w-full pl-9 pr-3 py-2 rounded-[9px] text-[13px] outline-none"
          style={{
            background: "var(--surf2)",
            border: "1.5px solid var(--line)",
            color: "var(--tx)",
          }}
        />
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
                {opt ? CONN_STATUS_LABEL[opt] : "Todos"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Riesgo</span>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {RISK_OPTIONS.map((opt) => (
              <button
                key={opt || "all"}
                onClick={() => onRiskChange(opt)}
                className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
                style={segStyle(risk === opt)}
              >
                {opt ? SEVERITY_LABEL[opt] : "Todos"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Sistema operativo</span>
          <select
            value={osFamily}
            onChange={(e) => onOsFamilyChange(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {osFamilies.map((fam) => (
              <option key={fam} value={fam}>{fam}</option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
