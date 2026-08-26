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
  view: "activas" | "todos";
  onViewChange: (v: "activas" | "todos") => void;
  statusOptions: FilterOption[];
  ruleOptions: FilterOption[];
}

const VIEW_OPTIONS: { value: "activas" | "todos"; label: string; icon: string }[] = [
  { value: "activas", label: "Activos", icon: "ph ph-pulse" },
  { value: "todos", label: "Historial", icon: "ph ph-clock-counter-clockwise" },
];

const SEVERITY_OPTIONS: { value: Severity | ""; label: string; tone?: string }[] = [
  { value: "", label: "Todas" },
  { value: "MEDIO", label: "Medio", tone: "var(--warn)" },
  { value: "ALTO", label: "Alto", tone: "var(--high)" },
  { value: "CRÍTICO", label: "Crítico", tone: "var(--crit)" },
];

const SINCE_OPTIONS: { value: "24h" | "7d" | "30d" | ""; label: string }[] = [
  { value: "", label: "Todo" },
  { value: "24h", label: "24 h" },
  { value: "7d", label: "7 d" },
  { value: "30d", label: "30 d" },
];

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
  view,
  onViewChange,
  statusOptions,
  ruleOptions,
}: Props) {
  const hasFilters = Boolean(search || status || severity || since || rule || view !== "activas");

  function reset() {
    onSearchChange("");
    onStatusChange("");
    onSeverityChange("");
    onSinceChange("");
    onRuleChange("");
    onViewChange("activas");
  }

  return (
    <section className="soc-panel rounded-2xl p-4 flex flex-col gap-4">
      <div className="flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="relative flex-1">
          <i className="ph ph-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2" style={{ fontSize: "15px", color: "var(--brand)" }} />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar por código, endpoint, IP o regla..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl text-[12px] outline-none transition-premium"
            style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx)", boxShadow: search ? "0 0 0 2px var(--brand-soft)" : "none" }}
          />
        </div>

        <div className="flex p-1 rounded-xl shrink-0" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {VIEW_OPTIONS.map((opt) => {
            const active = view === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => onViewChange(opt.value)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10.5px] font-semibold border-0 cursor-pointer transition-premium"
                style={active ? { background: "var(--brand)", color: "#fff", boxShadow: "0 5px 16px var(--brand-glow)" } : { background: "transparent", color: "var(--tx-mute)" }}
              >
                <i className={opt.icon} style={{ fontSize: "12px" }} />
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div className="flex items-center gap-1.5 mr-1">
          <i className="ph ph-funnel" style={{ fontSize: "13px", color: "var(--brand)" }} />
          <span className="text-[9px] font-bold tracking-[.13em] uppercase" style={{ color: "var(--tx-mute)" }}>Filtros</span>
        </div>

        <label className="flex items-center gap-2 rounded-xl px-2.5 py-1.5" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          <span className="text-[9px] font-semibold" style={{ color: "var(--tx-mute)" }}>Estado</span>
          <select value={status} onChange={(e) => onStatusChange(e.target.value as StatusBucket | "")} className="bg-transparent border-0 outline-none cursor-pointer text-[10px] font-semibold" style={{ color: "var(--tx-dim)" }}>
            <option value="">Todos</option>
            {statusOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>

        <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {SEVERITY_OPTIONS.map((opt) => {
            const active = severity === opt.value;
            return (
              <button
                key={opt.value || "all"}
                onClick={() => onSeverityChange(opt.value)}
                className="px-2.5 py-1.5 rounded-lg text-[10px] font-semibold border-0 cursor-pointer transition-premium"
                style={active ? { background: opt.tone ? `color-mix(in srgb, ${opt.tone} 14%, var(--surf3))` : "var(--brand-soft)", color: opt.tone || "var(--brand)" } : { background: "transparent", color: "var(--tx-mute)" }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {SINCE_OPTIONS.map((opt) => (
            <button
              key={opt.value || "all"}
              onClick={() => onSinceChange(opt.value)}
              className="px-2.5 py-1.5 rounded-lg text-[10px] font-semibold border-0 cursor-pointer transition-premium"
              style={since === opt.value ? { background: "var(--brand-soft)", color: "var(--brand)" } : { background: "transparent", color: "var(--tx-mute)" }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 min-w-[190px]" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          <span className="text-[9px] font-semibold whitespace-nowrap" style={{ color: "var(--tx-mute)" }}>Detección</span>
          <select value={rule} onChange={(e) => onRuleChange(e.target.value)} className="min-w-0 flex-1 bg-transparent border-0 outline-none cursor-pointer text-[10px] font-semibold" style={{ color: "var(--tx-dim)" }}>
            <option value="">Todas</option>
            {ruleOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>

        {hasFilters && (
          <button onClick={reset} className="ml-auto flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-semibold cursor-pointer border transition-premium btn-hover" style={{ background: "transparent", borderColor: "var(--line-soft)", color: "var(--tx-mute)" }}>
            <i className="ph ph-x" style={{ fontSize: "11px" }} />
            Limpiar filtros
          </button>
        )}
      </div>
    </section>
  );
}
