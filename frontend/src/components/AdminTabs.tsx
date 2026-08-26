export type AdminTab = "usuarios" | "agentes" | "configuracion" | "auditoria";

interface Props {
  tab: AdminTab;
  onChange: (tab: AdminTab) => void;
}

const TABS: { value: AdminTab; label: string; description: string; icon: string }[] = [
  { value: "usuarios", label: "Usuarios y roles", description: "Acceso y permisos", icon: "ph ph-users-three" },
  { value: "agentes", label: "Agentes", description: "Enrolamiento", icon: "ph ph-desktop-tower" },
  { value: "configuracion", label: "Configuración", description: "Parámetros operativos", icon: "ph ph-sliders-horizontal" },
  { value: "auditoria", label: "Auditoría", description: "Registro de actividad", icon: "ph ph-scroll" },
];

export default function AdminTabs({ tab, onChange }: Props) {
  return (
    <section className="soc-panel rounded-2xl p-2 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2">
      {TABS.map((t) => {
        const active = t.value === tab;
        return (
          <button
            key={t.value}
            onClick={() => onChange(t.value)}
            className="flex items-center gap-3 px-3.5 py-3 rounded-xl text-left cursor-pointer transition-premium"
            style={active ? { background: "var(--brand-fill)", color: "var(--brand)", border: "1px solid var(--brand-soft)", boxShadow: "inset 0 0 0 1px var(--brand-fill)" } : { background: "transparent", color: "var(--tx-dim)", border: "1px solid transparent" }}
          >
            <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: active ? "var(--brand-soft)" : "var(--surf2)", color: active ? "var(--brand)" : "var(--tx-mute)" }}>
              <i className={t.icon} style={{ fontSize: "16px" }} />
            </div>
            <div className="min-w-0">
              <div className="text-[10.5px] font-semibold truncate">{t.label}</div>
              <div className="text-[9px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>{t.description}</div>
            </div>
          </button>
        );
      })}
    </section>
  );
}
