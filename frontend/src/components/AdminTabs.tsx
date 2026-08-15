export type AdminTab = "usuarios" | "agentes" | "configuracion" | "auditoria";

interface Props {
  tab: AdminTab;
  onChange: (tab: AdminTab) => void;
}

const TABS: { value: AdminTab; label: string; icon: string }[] = [
  { value: "usuarios", label: "Usuarios y roles", icon: "ph ph-users" },
  { value: "agentes", label: "Agentes", icon: "ph ph-desktop-tower" },
  { value: "configuracion", label: "Configuración", icon: "ph ph-gear" },
  { value: "auditoria", label: "Registro de actividad", icon: "ph ph-scroll" },
];

export default function AdminTabs({ tab, onChange }: Props) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {TABS.map((t) => {
        const active = t.value === tab;
        return (
          <button
            key={t.value}
            onClick={() => onChange(t.value)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12.5px] font-medium border-0 cursor-pointer"
            style={
              active
                ? { background: "var(--brand-soft)", color: "var(--brand)" }
                : { background: "var(--surf2)", color: "var(--tx-mute)", border: "1px solid var(--line)" }
            }
          >
            <i className={t.icon} style={{ fontSize: "14px" }} />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
