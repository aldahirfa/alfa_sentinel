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

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-[12.5px] py-1.5">
      <span style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span className="font-medium text-right" style={{ color: "var(--tx)" }}>{value}</span>
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

  return (
    <section
      className="rounded-[10px] border p-4 flex flex-col gap-3.5"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Información personal</h3>

      {error && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
          Perfil actualizado.
        </div>
      )}

      <div className="flex flex-col gap-3 max-w-[420px]">
        <div>
          <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
            Nombre completo
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={fieldStyle}
          />
        </div>

        <div>
          <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
            Correo electrónico
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={fieldStyle}
          />
        </div>

        {dirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="self-start px-3.5 py-2 rounded-[8px] text-[12px] font-semibold border-0 cursor-pointer disabled:opacity-50"
            style={{ background: "var(--brand)", color: "#fff" }}
          >
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>
        )}
      </div>

      <div className="pt-3.5 border-t flex flex-col" style={{ borderColor: "var(--line-soft)" }}>
        <Field label="Username" value={data.username} />
        <Field label="Rol" value={roleLabel} />
        <Field
          label="Estado de la cuenta"
          value={
            <span style={{ color: data.is_active ? "var(--ok)" : "var(--crit)" }}>
              {data.is_active ? "Activa" : "Inactiva"}
            </span>
          }
        />
        <Field label="Último inicio de sesión" value={data.last_login_at ?? "—"} />
      </div>
    </section>
  );
}
