import type { Severity } from "../types/dashboard";
import type { AlertStatus, RuleOption } from "../types/alerts";
import { SEVERITY_LABEL } from "../lib/severity";

interface Props {
  search: string;
  onSearchChange: (v: string) => void;
  severity: Severity | "";
  onSeverityChange: (v: Severity | "") => void;
  status: AlertStatus | "";
  onStatusChange: (v: AlertStatus | "") => void;
  since: "24h" | "7d" | "30d" | "";
  onSinceChange: (v: "24h" | "7d" | "30d" | "") => void;
  rule: string;
  onRuleChange: (v: string) => void;
  rules: RuleOption[];
}

const SEVERITY_OPTIONS: (Severity | "")[] = ["", "SUSPICIOUS", "HIGH", "CRITICAL"];
const STATUS_OPTIONS: (AlertStatus | "")[] = ["", "NEW", "ACKNOWLEDGED", "ESCALATED", "CLOSED", "FALSE_POSITIVE"];
const STATUS_LABEL: Record<AlertStatus, string> = {
  NEW: "Nueva",
  ACKNOWLEDGED: "En investigación",
  ESCALATED: "Confirmada",
  CLOSED: "Cerrada",
  FALSE_POSITIVE: "Falso positivo",
};
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

export default function AlertsFilters({
  search,
  onSearchChange,
  severity,
  onSeverityChange,
  status,
  onStatusChange,
  since,
  onSinceChange,
  rule,
  onRuleChange,
  rules,
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
          placeholder="Buscar alerta, endpoint o descripción..."
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
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Severidad</span>
          <div className="flex p-0.5 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
            {SEVERITY_OPTIONS.map((opt) => (
              <button
                key={opt || "all"}
                onClick={() => onSeverityChange(opt)}
                className="px-2.5 py-1 rounded-md text-[11.5px] font-medium border-0 cursor-pointer"
                style={segStyle(severity === opt)}
              >
                {opt ? SEVERITY_LABEL[opt] : "Todas"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--tx-mute)" }}>Estado</span>
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value as AlertStatus | "")}
            className="px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium outline-none cursor-pointer"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {STATUS_OPTIONS.filter((o) => o).map((opt) => (
              <option key={opt} value={opt}>{STATUS_LABEL[opt as AlertStatus]}</option>
            ))}
          </select>
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
            {rules.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
