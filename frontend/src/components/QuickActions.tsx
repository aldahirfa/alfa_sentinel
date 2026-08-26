import type { Page } from "./ModuleMark";

const ACTIONS: { label: string; icon: string; page: Page; tone: "critical" | "brand" | "neutral" }[] = [
  { label: "Alertas críticas", icon: "ph ph-warning-octagon", page: "alerts", tone: "critical" },
  { label: "Incidentes activos", icon: "ph ph-siren", page: "incidentes", tone: "brand" },
  { label: "Endpoints aislados", icon: "ph ph-plugs", page: "endpoints", tone: "neutral" },
  { label: "Desplegar honeyfile", icon: "ph ph-file-plus", page: "honeyfiles", tone: "neutral" },
];

interface Props {
  onNavigate: (page: Page) => void;
  onPrefetch: (page: Page) => void;
}

export default function QuickActions({ onNavigate, onPrefetch }: Props) {
  return (
    <div
      className="soc-panel rounded-2xl px-4 py-3 flex items-center justify-between gap-4 flex-wrap"
      style={{ background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-command" style={{ fontSize: "15px" }} />
        </div>
        <div>
          <div className="text-[9.5px] tracking-[.15em] uppercase font-bold" style={{ color: "var(--brand)" }}>
            Centro de operación
          </div>
          <div className="text-[10px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
            Accesos directos para investigación y respuesta
          </div>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {ACTIONS.map(({ label, icon, page, tone }) => {
          const critical = tone === "critical";
          const brand = tone === "brand";
          return (
            <button
              key={label}
              type="button"
              onMouseEnter={() => onPrefetch(page)}
              onFocus={() => onPrefetch(page)}
              onClick={() => onNavigate(page)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-[10px] font-semibold transition-premium btn-hover border cursor-pointer"
              style={
                critical
                  ? { borderColor: "var(--crit-soft)", background: "var(--crit-fill)", color: "var(--crit)" }
                  : brand
                    ? { borderColor: "var(--brand-soft)", background: "var(--brand-fill)", color: "var(--brand)" }
                    : { borderColor: "var(--line-soft)", background: "var(--surf2)", color: "var(--tx-dim)" }
              }
            >
              <i className={icon} style={{ fontSize: "13px" }} />
              {label}
              <i className="ph ph-arrow-up-right" style={{ fontSize: "10px", opacity: .65 }} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
