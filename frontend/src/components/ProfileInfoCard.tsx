import { useState } from "react";
import { updateProfile } from "../api/client";
import type { ProfileResponse } from "../types/perfil";

interface Props {
  data: ProfileResponse;
  roleLabel: string;
  onSaved: () => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line)",
  color: "var(--tx)",
};

function Field({ label, value, icon }: { label: string; value: React.ReactNode; icon: string }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b last:border-b-0" style={{ borderColor: "var(--line-soft)" }}>
      <span className="w-8 h-8 rounded-lg grid place-items-center shrink-0" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>
        <i className={icon} style={{ fontSize: "13px" }} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[9px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>{label}</div>
        <div className="text-[11px] font-medium mt-1 truncate" style={{ color: "var(--tx)" }}>{value}</div>
      </div>
    </div>
  );
}

export default function ProfileInfoCard({ data, roleLabel, onSaved }: Props) {
  const [fullName, setFullName] = useState(data.full_name);
  const [email, setEmail] = useState(data.email ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const dirty = fullName !== data.full_name || email !== (data.email ?? "");

  async function handleSave() {
    if (!fullName.trim()) {
      setError("El nombre completo no puede quedar vacío.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateProfile({ full_name: fullName.trim(), email: email.trim() || null });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el perfil.");
    } finally {
      setSaving(false);
    }
  }

  const initials = (data.full_name || data.username)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-11 h-11 rounded-2xl grid place-items-center text-[13px] font-bold" style={{ background: "var(--brand-soft)", color: "var(--brand)", border: "1px solid var(--brand-soft)" }}>
          {initials || "U"}
        </div>
        <div className="min-w-0">
          <div className="text-[9px] font-bold tracking-[.14em] uppercase" style={{ color: "var(--brand)" }}>Información de cuenta</div>
          <div className="text-[13px] font-semibold mt-0.5 truncate" style={{ color: "var(--tx)" }}>{data.full_name || data.username}</div>
          <div className="text-[9.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>@{data.username} · {roleLabel}</div>
        </div>
      </div>

      <div className="p-5">
        {error && <div className="rounded-xl px-3 py-2.5 text-[10px] mb-4" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>{error}</div>}
        {saved && <div className="rounded-xl px-3 py-2.5 text-[10px] mb-4" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>Perfil actualizado correctamente.</div>}

        <div className="flex flex-col gap-3">
          <div>
            <label className="text-[9.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Nombre completo</label>
            <div className="relative">
              <i className="ph ph-identification-card absolute left-3 top-1/2 -translate-y-1/2" style={{ fontSize: "14px", color: "var(--tx-mute)" }} />
              <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full pl-9 pr-3 py-2.5 rounded-xl text-[11px] outline-none transition-premium" style={fieldStyle} />
            </div>
          </div>

          <div>
            <label className="text-[9.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Correo electrónico</label>
            <div className="relative">
              <i className="ph ph-envelope-simple absolute left-3 top-1/2 -translate-y-1/2" style={{ fontSize: "14px", color: "var(--tx-mute)" }} />
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full pl-9 pr-3 py-2.5 rounded-xl text-[11px] outline-none transition-premium" style={fieldStyle} />
            </div>
          </div>

          <div className="min-h-[34px]">
            {dirty && (
              <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-semibold border-0 cursor-pointer disabled:opacity-50 transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff", boxShadow: "var(--shadow-blue)" }}>
                <i className={saving ? "ph ph-spinner" : "ph ph-floppy-disk"} />
                {saving ? "Guardando..." : "Guardar cambios"}
              </button>
            )}
          </div>
        </div>

        <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--line-soft)" }}>
          <Field label="Usuario" value={data.username} icon="ph ph-at" />
          <Field label="Rol" value={roleLabel} icon="ph ph-shield-check" />
          <Field label="Estado" value={<span style={{ color: data.is_active ? "var(--ok)" : "var(--crit)" }}>{data.is_active ? "Cuenta activa" : "Cuenta inactiva"}</span>} icon="ph ph-pulse" />
          <Field label="Último inicio de sesión" value={data.last_login_at ?? "Sin registro"} icon="ph ph-clock-counter-clockwise" />
        </div>
      </div>
    </section>
  );
}
