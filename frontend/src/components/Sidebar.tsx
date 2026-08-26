export type Page = "dashboard" | "endpoints" | "alerts" | "incidentes" | "honeyfiles" | "reglas" | "respuesta" | "reportes" | "administracion" | "perfil";

interface Props {
  alertsActive: number;
  incidentsActive: number;
  page: Page;
  onNavigate: (page: Page) => void;
}

type NavItem = {
  label: string;
  page: Page;
  badgeKey?: "alerts" | "incidents";
};

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "OPERACIÓN",
    items: [
      { label: "Panel de control", page: "dashboard" },
      { label: "Endpoints", page: "endpoints" },
      { label: "Alertas", page: "alerts", badgeKey: "alerts" },
      { label: "Incidentes", page: "incidentes", badgeKey: "incidents" },
    ],
  },
  {
    label: "DETECCIÓN Y RESPUESTA",
    items: [
      { label: "Honeyfiles", page: "honeyfiles" },
      { label: "Reglas heurísticas", page: "reglas" },
      { label: "Acciones de respuesta", page: "respuesta" },
    ],
  },
  {
    label: "GESTIÓN",
    items: [
      { label: "Reportes", page: "reportes" },
      { label: "Administración", page: "administracion" },
    ],
  },
];

function ModuleMark({ page }: { page: Page }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.65,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  return (
    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
      {page === "dashboard" && (
        <>
          <path {...common} d="M4.25 5.25h6.2v5.5h-6.2zM13.55 5.25h6.2v3.35h-6.2zM13.55 11.7h6.2v7.05h-6.2zM4.25 13.7h6.2v5.05h-6.2z" />
          <circle cx="17.7" cy="7" r=".85" fill="currentColor" />
        </>
      )}
      {page === "endpoints" && (
        <>
          <rect {...common} x="3.5" y="4.5" width="17" height="11.5" rx="2.2" />
          <path {...common} d="M8.2 19.5h7.6M12 16v3.5" />
          <circle cx="17.1" cy="8.3" r="1.15" fill="currentColor" />
        </>
      )}
      {page === "alerts" && (
        <>
          <path {...common} d="M10.2 4.25 3.7 17.05a1.85 1.85 0 0 0 1.65 2.7h13.3a1.85 1.85 0 0 0 1.65-2.7L13.8 4.25a2 2 0 0 0-3.6 0Z" />
          <path {...common} d="M12 8.2v5.15" />
          <circle cx="12" cy="16.65" r="1" fill="currentColor" />
        </>
      )}
      {page === "incidentes" && (
        <>
          <path {...common} d="m12 3.35 7.25 4.2v8.9L12 20.65l-7.25-4.2v-8.9z" />
          <circle {...common} cx="12" cy="12" r="3.25" />
          <path {...common} d="M12 6.8v1.9M12 15.3v1.9M6.8 12h1.9M15.3 12h1.9" />
        </>
      )}
      {page === "honeyfiles" && (
        <>
          <path {...common} d="M6 3.7h7l5 5v11.6H6z" />
          <path {...common} d="M13 3.7v5h5" />
          <circle {...common} cx="11.2" cy="14.1" r="2.35" />
          <path {...common} d="m12.9 15.8 2.05 2.05" />
        </>
      )}
      {page === "reglas" && (
        <>
          <path {...common} d="M5 6h14M5 12h14M5 18h14" />
          <circle cx="9" cy="6" r="1.65" fill="#0a111e" stroke="currentColor" strokeWidth="1.65" />
          <circle cx="15" cy="12" r="1.65" fill="#0a111e" stroke="currentColor" strokeWidth="1.65" />
          <circle cx="11" cy="18" r="1.65" fill="#0a111e" stroke="currentColor" strokeWidth="1.65" />
        </>
      )}
      {page === "respuesta" && (
        <>
          <path {...common} d="M12 3.35c2.35 1.75 4.9 2.25 7.15 2.55v5.55c0 4.05-2.45 7.35-7.15 9.2-4.7-1.85-7.15-5.15-7.15-9.2V5.9C7.1 5.6 9.65 5.1 12 3.35Z" />
          <path {...common} d="m13.15 7.7-3.4 4.75h2.65l-1.15 3.85 3.45-5h-2.65z" />
        </>
      )}
      {page === "reportes" && (
        <>
          <path {...common} d="M5.2 3.75h9.1l4.5 4.5v12H5.2z" />
          <path {...common} d="M14.3 3.75v4.5h4.5M8.3 16.7v-2.4M11.5 16.7v-4.9M14.7 16.7v-7" />
        </>
      )}
      {page === "administracion" && (
        <>
          <path {...common} d="M12 3.4 19.1 7.5v8.2L12 19.8l-7.1-4.1V7.5z" />
          <circle {...common} cx="12" cy="11.6" r="2.55" />
          <path {...common} d="M8.1 17.25c.65-1.6 2.05-2.55 3.9-2.55s3.25.95 3.9 2.55" />
        </>
      )}
    </svg>
  );
}

export default function Sidebar({ alertsActive, incidentsActive, page, onNavigate }: Props) {
  const badgeValue = { alerts: alertsActive, incidents: incidentsActive };

  return (
    <aside
      className="w-[248px] shrink-0 border-r flex flex-col sticky top-0 h-screen overflow-hidden"
      style={{
        background: "linear-gradient(180deg, #0a111e 0%, #080d17 58%, #070b13 100%)",
        borderColor: "#17243a",
        boxShadow: "18px 0 50px rgba(0,0,0,.08)",
      }}
    >
      <div className="h-[3px] flex shrink-0">
        <div className="flex-1" style={{ background: "#DA291C", opacity: ".72" }} />
        <div className="flex-1" style={{ background: "#F4E400", opacity: ".72" }} />
        <div className="flex-1" style={{ background: "#007A33", opacity: ".72" }} />
      </div>

      <div className="relative px-[18px] pt-5 pb-5 border-b" style={{ borderColor: "#121f32" }}>
        <div
          className="absolute inset-x-4 top-0 h-24 pointer-events-none"
          style={{ background: "radial-gradient(circle at 18% 10%, rgba(77,141,255,.13), transparent 68%)" }}
        />
        <div className="relative flex gap-3 items-center">
          <div
            className="w-10 h-10 shrink-0 rounded-xl border flex items-center justify-center overflow-hidden"
            style={{
              background: "linear-gradient(145deg, rgba(77,141,255,.18), rgba(56,189,248,.07))",
              borderColor: "rgba(77,141,255,.30)",
              boxShadow: "0 10px 30px rgba(34,98,220,.12)",
            }}
          >
            <img src="/static/logo-icon.png" alt="Sistema ALFA-Sentinel" className="w-[26px] h-auto" />
          </div>
          <div className="min-w-0">
            <div className="text-[14px] font-bold tracking-[.02em] text-[#f4f7fb]">ALFA-Sentinel</div>
            <div className="text-[10px] leading-[1.35] mt-1 text-[#6f819a]">Consola central de seguridad</div>
          </div>
        </div>
      </div>

      <nav className="px-3.5 pt-4 pb-3 flex-1 overflow-auto">
        {NAV_GROUPS.map((group, groupIndex) => (
          <div key={group.label} className={groupIndex === 0 ? "" : "mt-5"}>
            <div className="px-2.5 mb-2 text-[9px] font-bold tracking-[.16em] text-[#50617a]">{group.label}</div>
            <div className="flex flex-col gap-1">
              {group.items.map((item) => {
                const active = item.page === page;
                const badge = item.badgeKey ? badgeValue[item.badgeKey] : null;
                const badgeCritical = item.badgeKey === "alerts";

                return (
                  <a
                    key={item.label}
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      onNavigate(item.page);
                    }}
                    className="relative group flex items-center gap-3 px-3 py-[9px] rounded-[10px] no-underline text-[12.5px] font-medium transition-premium overflow-hidden"
                    style={
                      active
                        ? {
                            color: "#dce9ff",
                            background: "linear-gradient(90deg, rgba(77,141,255,.16), rgba(77,141,255,.07))",
                            border: "1px solid rgba(77,141,255,.15)",
                            boxShadow: "inset 3px 0 0 #4d8dff, 0 8px 26px rgba(25,87,194,.07)",
                          }
                        : { color: "#8191a8", border: "1px solid transparent" }
                    }
                  >
                    <div
                      className="w-7 h-7 rounded-[8px] grid place-items-center shrink-0 transition-premium"
                      style={{
                        background: active ? "rgba(77,141,255,.12)" : "rgba(255,255,255,.018)",
                        color: active ? "#65a2ff" : "#71839c",
                        border: active ? "1px solid rgba(77,141,255,.14)" : "1px solid rgba(255,255,255,.025)",
                      }}
                    >
                      <ModuleMark page={item.page} />
                    </div>
                    <span className="truncate">{item.label}</span>
                    {badge !== null && badge > 0 && (
                      <span
                        className="ml-auto min-w-[23px] h-[21px] px-1.5 rounded-full grid place-items-center text-[9.5px] font-bold"
                        style={{
                          background: badgeCritical ? "rgba(251,92,112,.12)" : "rgba(251,146,60,.12)",
                          color: badgeCritical ? "#ff7588" : "#ffad6b",
                          border: `1px solid ${badgeCritical ? "rgba(251,92,112,.20)" : "rgba(251,146,60,.20)"}`,
                        }}
                      >
                        {badge > 99 ? "99+" : badge}
                      </span>
                    )}
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-4 py-4 border-t" style={{ borderColor: "#152136" }}>
        <div className="flex gap-3 items-center">
          <div
            className="w-[58px] h-9 shrink-0 rounded-lg flex items-center justify-center overflow-hidden"
            style={{ background: "rgba(255,255,255,.025)", border: "1px solid #1a2940" }}
          >
            <img src="/static/logo_main_white.png" alt="AGETIC" className="max-w-[50px] max-h-[27px] object-contain" />
          </div>
          <div className="text-[9.5px] leading-[1.35] text-[#53657e]">
            AGETIC · Estado Plurinacional
            <br />
            de Bolivia
          </div>
        </div>
      </div>
    </aside>
  );
}
