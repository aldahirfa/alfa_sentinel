// Solo navegación hacia pantallas reales que ya existen (Jinja2) --
// nada de esto ejecuta una acción directa sobre un sistema operativo
// desde el dashboard.
const ACTIONS = [
  { label: "Ver alertas críticas", icon: "ph ph-warning-octagon", href: "/incidentes?severity=CRITICAL", critical: true },
  { label: "Ver incidentes activos", icon: "ph ph-siren", href: "/incidentes" },
  { label: "Ver endpoints aislados", icon: "ph ph-plugs", href: "/endpoints" },
  { label: "Crear honeyfile", icon: "ph ph-file-plus", href: "/honeyfiles" },
];

export default function QuickActions() {
  return (
    <div className="flex items-center gap-2.5 flex-wrap">
      <span className="text-[10.5px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
        Acciones rápidas
      </span>
      <div className="flex gap-2 flex-wrap">
        {ACTIONS.map(({ label, icon, href, critical }) => (
          <a
            key={label}
            href={href}
            className="flex items-center gap-2 px-3 py-2 rounded-lg no-underline text-xs font-bold tracking-wide transition-premium btn-hover shadow-sm"
            style={
              critical
                ? { border: "1px solid var(--crit-soft)", background: "var(--crit-fill)", color: "var(--crit)" }
                : { border: "1px solid var(--line-soft)", background: "var(--surf2)", color: "var(--tx-dim)" }
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
