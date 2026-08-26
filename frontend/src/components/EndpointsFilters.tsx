import type { ConnStatus } from "../types/endpoints";
import type { Severity } from "../types/dashboard";
import { CONN_STATUS_LABEL } from "../lib/endpointStatus";

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

const STATUS_OPTIONS: { value: ConnStatus | ""; label: string; tone?: string }[] = [
  { value: "", label: "Todos" },
  { value: "ONLINE", label: CONN_STATUS_LABEL.ONLINE, tone: "var(--ok)" },
  { value: "OFFLINE", label: CONN_STATUS_LABEL.OFFLINE, tone: "var(--off)" },
  { value: "ISOLATED", label: CONN_STATUS_LABEL.ISOLATED, tone: "var(--crit)" },
];

const RISK_OPTIONS: { value: Severity | ""; label: string; tone?: string }[] = [
  { value: "", label: "Todos" },
  { value: "BAJO", label: "Bajo", tone: "var(--ok)" },
  { value: "MEDIO", label: "Medio", tone: "var(--warn)" },
  { value: "ALTO", label: "Alto", tone: "var(--high)" },
  { value: "CRÍTICO", label: "Crítico", tone: "var(--crit)" },
];

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
  const hasFilters = Boolean(search || status || risk || osFamily);

  function reset() {
    onSearchChange("");
    onStatusChange("");
    onRiskChange("");
    onOsFamilyChange("");
  }

  return (
    <section className="soc-panel rounded-2xl p-4 flex flex-col gap-4">
      <div className="relative">
        <i className="ph ph-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2" style={{ fontSize: "15px", color: "var(--brand)" }} />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Buscar por hostname, dirección IP o sistema operativo..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl text-[12px] outline-none transition-premium"
          style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx)", boxShadow: search ? "0 0 0 2px var(--brand-soft)" : "none" }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2.5 pt-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div className="flex items-center gap-1.5 mr-1">
          <i className="ph ph-funnel" style={{ fontSize: "13px", color: "var(--brand)" }} />
          <span className="text-[9px] font-bold tracking-[.13em] uppercase" style={{ color: "var(--tx-mute)" }}>Filtros</span>
        </div>

        <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {STATUS_OPTIONS.map((opt) => {
            const active = status === opt.value;
            return (
              <button
                key={opt.value || "all"}
                onClick={() => onStatusChange(opt.value)}
                className="px-2.5 py-1.5 rounded-lg text-[10px] font-semibold border-0 cursor-pointer transition-premium"
                style={active
                  ? { background: opt.tone ? `color-mix(in srgb, ${opt.tone} 13%, var(--surf3))` : "var(--brand-soft)", color: opt.tone || "var(--brand)" }
                  : { background: "transparent", color: "var(--tx-mute)" }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <div className="flex p-1 rounded-xl" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          {RISK_OPTIONS.map((opt) => {
            const active = risk === opt.value;
            return (
              <button
                key={opt.value || "all"}
                onClick={() => onRiskChange(opt.value)}
                className="px-2.5 py-1.5 rounded-lg text-[10px] font-semibold border-0 cursor-pointer transition-premium"
                style={active
                  ? { background: opt.tone ? `color-mix(in srgb, ${opt.tone} 13%, var(--surf3))` : "var(--brand-soft)", color: opt.tone || "var(--brand)" }
                  : { background: "transparent", color: "var(--tx-mute)" }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <label className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 min-w-[170px]" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          <span className="text-[9px] font-semibold whitespace-nowrap" style={{ color: "var(--tx-mute)" }}>Sistema operativo</span>
          <select
            value={osFamily}
            onChange={(e) => onOsFamilyChange(e.target.value)}
            className="min-w-0 flex-1 bg-transparent border-0 outline-none cursor-pointer text-[10px] font-semibold"
            style={{ color: "var(--tx-dim)" }}
          >
            <option value="">Todos</option>
            {osFamilies.map((fam) => <option key={fam} value={fam}>{fam}</option>)}
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
