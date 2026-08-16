// Réplica del sidebar del mockup real (Panel de control AGETIC/...dc.html):
// franja de bandera boliviana, logo, nav con badges de conteo real,
// pie con identidad AGETIC. Todos los ítems tienen pantalla real en
// React (ver App.tsx, navegación interna sin recargar) -- la
// migración progresiva desde Jinja2 terminó acá (2026-08-15).

// "perfil" no está en NAV_ITEMS -- se llega a esa pantalla desde el
// menú de usuario ("Mi perfil" en UserMenu.tsx), no desde el sidebar,
// igual que en la vieja página Jinja2 (perfil.html tampoco estaba en
// el nav lateral).
export type Page = "dashboard" | "endpoints" | "alerts" | "incidentes" | "honeyfiles" | "reglas" | "respuesta" | "reportes" | "administracion" | "perfil";

interface Props {
  alertsActive: number;
  incidentsActive: number;
  page: Page;
  onNavigate: (page: Page) => void;
}

const NAV_ITEMS: {
  label: string;
  icon: string;
  href?: string;
  page?: Page;
  badgeKey?: "alerts" | "incidents";
}[] = [
  { label: "Panel de control", icon: "ph-fill ph-squares-four", page: "dashboard" },
  { label: "Endpoints", icon: "ph ph-desktop-tower", page: "endpoints" },
  { label: "Alertas", icon: "ph ph-warning", page: "alerts", badgeKey: "alerts" },
  { label: "Incidentes", icon: "ph ph-siren", page: "incidentes", badgeKey: "incidents" },
  { label: "Honeyfiles", icon: "ph ph-file-lock", page: "honeyfiles" },
  { label: "Reglas heurísticas", icon: "ph ph-list-checks", page: "reglas" },
  { label: "Acciones de respuesta", icon: "ph ph-lightning", page: "respuesta" },
  { label: "Reports", icon: "ph ph-chart-bar", page: "reportes" },
  { label: "Administración", icon: "ph ph-gear", page: "administracion" },
];

export default function Sidebar({ alertsActive, incidentsActive, page, onNavigate }: Props) {
  const badgeValue = { alerts: alertsActive, incidents: incidentsActive };

  return (
    <aside className="w-[232px] shrink-0 bg-[var(--surf)] border-r border-[var(--line)] flex flex-col sticky top-0 h-screen">
      {/* Franja bandera boliviana -- identidad AGETIC, no es un dato del sistema */}
      <div className="h-[3px] flex">
        <div className="flex-1" style={{ background: "#DA291C", opacity: "var(--band-op)" }} />
        <div className="flex-1" style={{ background: "#F4E400", opacity: "var(--band-op)" }} />
        <div className="flex-1" style={{ background: "#007A33", opacity: "var(--band-op)" }} />
      </div>

      <div className="px-4 pt-[18px] pb-3.5 flex gap-2.5 items-start">
        <div className="w-8 h-8 shrink-0 rounded-lg bg-[var(--brand-soft)] border border-[var(--brand)] flex items-center justify-center overflow-hidden">
          <img src="/static/logo-icon.png" alt="ALFA_SENTINEL" className="w-[22px] h-auto" />
        </div>
        <div className="min-w-0">
          <div className="text-[14.5px] font-semibold tracking-wide text-[var(--tx)]">ALFA_SENTINEL</div>
          <div className="text-[10.5px] leading-tight mt-0.5 text-[var(--tx-mute)]">
            Early Ransomware
            <br />
            Detection &amp; Response
          </div>
        </div>
      </div>

      <nav className="px-3 py-2 flex flex-col gap-1 flex-1 overflow-auto">
        {NAV_ITEMS.map((item) => {
          const { label, icon, href, page: itemPage, badgeKey } = item;
          const active = itemPage !== undefined && itemPage === page;
          const badge = badgeKey ? badgeValue[badgeKey] : null;

          const content = (
            <>
              <i className={icon} style={{ fontSize: "16px" }} />
              {label}
              {badge !== null && badge > 0 && (
                <span
                  className="ml-auto text-[10.5px] font-bold px-2 py-0.5 rounded-full tracking-wide shadow-sm"
                  style={{
                    background: badgeKey === "alerts" ? "var(--crit-fill)" : "var(--high-fill)",
                    color: badgeKey === "alerts" ? "var(--crit)" : "var(--high)",
                    border: `1px solid ${badgeKey === "alerts" ? "var(--crit-soft)" : "var(--high-soft)"}`
                  }}
                >
                  {badge}
                </span>
              )}
            </>
          );

          const sharedProps = {
            key: label,
            className:
              "flex items-center gap-3 px-3 py-2.5 rounded-lg no-underline text-[13.5px] font-medium transition-premium cursor-pointer",
            style: active
              ? { color: "var(--brand)", background: "var(--brand-fill)", boxShadow: "inset 3px 0 0 var(--brand)" }
              : { color: "var(--tx-dim)" },
            onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
              if (!active) {
                e.currentTarget.style.background = "var(--surf2)";
                e.currentTarget.style.color = "var(--tx)";
              }
            },
            onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
              if (!active) {
                e.currentTarget.style.background = "";
                e.currentTarget.style.color = "var(--tx-dim)";
              }
            },
          };

          if (itemPage) {
            return (
              <a {...sharedProps} href="#" onClick={(e) => { e.preventDefault(); onNavigate(itemPage); }}>
                {content}
              </a>
            );
          }
          return (
            <a {...sharedProps} href={href}>
              {content}
            </a>
          );
        })}
      </nav>

      <div className="px-4 py-3.5 border-t border-[var(--line-soft)] flex gap-2.5 items-center">
        <div className="w-[22px] h-[22px] shrink-0 rounded-[5px] bg-[var(--surf3)] grid place-items-center text-[9px] font-bold tracking-wide text-[var(--tx-dim)]">
          AG
        </div>
        <div className="text-[9.5px] leading-tight text-[var(--tx-mute)]">
          AGETIC · Estado Plurinacional
          <br />
          de Bolivia
        </div>
      </div>
    </aside>
  );
}
