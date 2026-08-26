import { ModuleMark, type Page } from "./ModuleMark";
export type { Page } from "./ModuleMark";

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
        <div className="absolute inset-x-4 top-0 h-24 pointer-events-none" style={{ background: "radial-gradient(circle at 18% 10%, rgba(77,141,255,.13), transparent 68%)" }} />
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
          <div className="w-[58px] h-9 shrink-0 rounded-lg flex items-center justify-center overflow-hidden" style={{ background: "rgba(255,255,255,.025)", border: "1px solid #1a2940" }}>
            <img src="/static/logo_agetic.png" alt="AGETIC" className="max-w-[50px] max-h-[27px] object-contain" />
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
