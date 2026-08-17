import type { Severity } from "../types/dashboard";
import type { FilterOption, StatusBucket } from "../types/incidentes";

interface Props {
  search: string;
  onSearchChange: (v: string) => void;
  status: StatusBucket | "";
  onStatusChange: (v: StatusBucket | "") => void;
  severity: Severity | "";
  onSeverityChange: (v: Severity | "") => void;
  since: "24h" | "7d" | "30d" | "";
  onSinceChange: (v: "24h" | "7d" | "30d" | "") => void;
  rule: string;
  onRuleChange: (v: string) => void;
  statusOptions: FilterOption[];
  ruleOptions: FilterOption[];
}

const SEVERITY_OPTIONS: (Severity | "")[] = ["", "MEDIO", "ALTO", "CRÍTICO"];
const SINCE_OPTIONS: { value: "24h" | "7d" | "30d" | ""; label: string }[] = [
  { value: "", label: "Todo" },
  { value: "24h", label: "24 h" },
  { value: "7d", label: "7 días" },
  { value: "30d", label: "30 días" },
];

function segStyle(active: boolean): React.CSSProperties {
  return active
    ? { background: "var(--brand-soft)", color: "var(--brand)" }
    : { background: "transparent", color: "var(--tx-mute)" };
}

export default function IncidentesFilters({
  search,
  onSearchChange,
  status,
  onStatusChange,
  severity,
  onSeverityChange,
  since,
  onSinceChange,
  rule,
  onRuleChange,
  statusOptions,
  ruleOptions,
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
          placeholder="Buscar por endpoint, IP, código o regla..."
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
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value as StatusBucket | "")}
            className="px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {statusOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Severidad</span>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {SEVERITY_OPTIONS.map((opt) => (
              <button
                key={opt || "all"}
                onClick={() => onSeverityChange(opt)}
                className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
                style={segStyle(severity === opt)}
              >
                {opt || "Todas"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Periodo</span>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {SINCE_OPTIONS.map((opt) => (
              <button
                key={opt.value || "all"}
                onClick={() => onSinceChange(opt.value)}
                className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
                style={segStyle(since === opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Tipo de detección</span>
          <select
            value={rule}
            onChange={(e) => onRuleChange(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {ruleOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
