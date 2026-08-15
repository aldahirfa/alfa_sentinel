import { useState } from "react";
import { createUser, updateUserAccount } from "../api/client";
import type { AdminUser } from "../types/admin";

interface Props {
  mode: "create" | "edit";
  user: AdminUser | null;
  onClose: () => void;
  onSaved: () => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line)",
  color: "var(--tx)",
};

export default function UserFormModal({ mode, user, onClose, onSaved }: Props) {
  const [username, setUsername] = useState(user?.username ?? "");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [role, setRole] = useState(user?.roles?.split(",")[0]?.trim() ?? "admin");
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setError(null);
    if (mode === "create") {
      if (!username.trim() || !fullName.trim() || password.length < 8) {
        setError("Usuario, nombre completo y una contraseña de al menos 8 caracteres son obligatorios.");
        return;
      }
    }
    setSaving(true);
    try {
      if (mode === "create") {
        await createUser({
          username: username.trim(),
          password,
          full_name: fullName.trim(),
          email: email.trim() || null,
          role: role.trim() || "admin",
        });
      } else if (user) {
        await updateUserAccount(user.id, {
          full_name: fullName.trim(),
          email: email.trim(),
          is_active: isActive,
          role: role.trim(),
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el usuario.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-40" style={{ background: "rgba(0,0,0,0.5)" }} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="w-full max-w-md rounded-[12px] border flex flex-col"
          style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "0 20px 60px rgba(0,0,0,.4)" }}
        >
          <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "var(--line-soft)" }}>
            <div className="text-[15px] font-semibold" style={{ color: "var(--tx)" }}>
              {mode === "create" ? "Nuevo usuario" : `Editar ${user?.username}`}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>

          <div className="px-5 py-4 flex flex-col gap-3">
            {error && (
              <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                {error}
              </div>
            )}

            {mode === "create" && (
              <div>
                <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Usuario</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
                  style={fieldStyle}
                />
              </div>
            )}

            <div>
              <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Nombre completo</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
                style={fieldStyle}
              />
            </div>

            <div>
              <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Correo</label>
              <input
                type="email"
                value={email ?? ""}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
                style={fieldStyle}
              />
            </div>

            {mode === "create" && (
              <div>
                <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Contraseña (mínimo 8 caracteres)</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
                  style={fieldStyle}
                />
              </div>
            )}

            <div>
              <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Rol</label>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
                style={fieldStyle}
              />
              <p className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
                Hoy solo existe el rol <code>admin</code> en el sistema -- solo 2 endpoints (crear/editar usuarios y generar tokens de agente) distinguen por rol.
              </p>
            </div>

            {mode === "edit" && (
              <label className="flex items-center gap-2 cursor-pointer text-[13px]" style={{ color: "var(--tx)" }}>
                <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
                Cuenta activa
              </label>
            )}
          </div>

          <div className="px-5 py-3.5 border-t flex justify-end gap-2" style={{ borderColor: "var(--line-soft)" }}>
            <button
              onClick={onClose}
              className="px-3.5 py-2 rounded-[8px] text-[12.5px] font-medium cursor-pointer"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 rounded-[8px] text-[12.5px] font-semibold cursor-pointer border-0 disabled:opacity-50"
              style={{ background: "var(--brand)", color: "#fff" }}
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
