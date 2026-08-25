const ACTIONS = [
  { label: "Alertas críticas", icon: "ph ph-warning-octagon", href: "/incidentes?severity=CRITICAL", critical: true },
  { label: "Incidentes activos", icon: "ph ph-siren", href: "/incidentes" },
  { label: "Endpoints aislados", icon: "ph ph-plugs", href: "/endpoints" },
  { label: "Desplegar honeyfile", icon: "ph ph-file-plus", href: "/honeyfiles" },
];

export default function QuickActions() {
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <div className="text-[10px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--brand)" }}>
          Operación
        </div>
        <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
          Accesos directos para investigación y respuesta
        </div>
      </div>
      <div className="flex gap-2 flex-wrap">
        {ACTIONS.map(({ label, icon, href, critical }) => (
          <a
            key={label}
            href={href}
            className="flex items-center gap-2 px-3 py-2 rounded-[10px] no-underline text-[10.5px] font-semibold transition-premium btn-hover border"
            style={
              critical
                ? {
                    borderColor: "var(--crit-soft)",
                    background: "var(--crit-fill)",
                    color: "var(--crit)",
                  }
                : {
                    borderColor: "var(--line-soft)",
                    background: "var(--surf2)",
                    color: "var(--tx-dim)",
                    boxShadow: "var(--shadow)",
                  }
            }
          >
            <i className={icon} style={{ fontSize: "14px" }} />
            {label}
          </a>
        ))}
      </div>
    </div>
  );
}
