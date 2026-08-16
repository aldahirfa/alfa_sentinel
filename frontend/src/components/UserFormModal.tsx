import { useState, useEffect } from "react";
import { createUser, fetchRoles, updateUserAccount } from "../api/client";
import type { AdminUser, Role } from "../types/admin";

interface Props {
  mode: "create" | "edit";
  user: AdminUser | null;
  onClose: () => void;
  onSaved: () => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line-soft)",
  color: "var(--tx)",
};

export default function UserFormModal({ mode, user, onClose, onSaved }: Props) {
  const [username, setUsername] = useState(user?.username ?? "");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [role, setRole] = useState(user?.roles?.split(",")[0]?.trim() ?? "");
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Roles reales desde GET /api/roles -- no una lista hardcodeada en
  // React (2026-08-16, ver PENDIENTES.md). Si mañana se agrega un rol
  // nuevo en la BD, aparece acá solo con recargar.
  const [roles, setRoles] = useState<Role[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);
  const [rolesError, setRolesError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRoles()
      .then((res) => {
        if (cancelled) return;
        setRoles(res.roles);
        // Si no había un rol preseleccionado (alta) o el rol actual del
        // usuario ya no existe en el catálogo, se preselecciona el
        // primero de la lista real en vez de asumir "admin".
        setRole((current) => {
          if (current && res.roles.some((r) => r.name === current)) return current;
          return res.roles[0]?.name ?? "";
        });
      })
      .catch(() => {
        if (!cancelled) setRolesError("No se pudieron cargar los roles.");
      })
      .finally(() => {
        if (!cancelled) setRolesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setError(null);
    if (mode === "create") {
      if (!username.trim() || !fullName.trim() || password.length < 8) {
        setError("Usuario, nombre completo y una contraseña de al menos 8 caracteres son obligatorios.");
        return;
      }
    }
    if (!role) {
      setError("Elegí un rol -- no se pudieron cargar los roles disponibles.");
      return;
    }
    setSaving(true);
    try {
      if (mode === "create") {
        await createUser({
          username: username.trim(),
          password,
          full_name: fullName.trim(),
          email: email.trim() || null,
          role,
        });
      } else if (user) {
        await updateUserAccount(user.id, {
          full_name: fullName.trim(),
          email: email.trim(),
          is_active: isActive,
          role,
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el usuario.");
    } finally {
      setSaving(false);
    }
  }

  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <>
      <div 
        onClick={onClose} 
        className="fixed inset-0 z-40" 
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }} 
      />
      <div 
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{
          opacity: entered ? 1 : 0,
          transform: entered ? "scale(1)" : "scale(0.95)",
          transition: "opacity 200ms ease, transform 200ms ease",
        }}
      >
        <div
          className="w-full max-w-md rounded-2xl border flex flex-col shadow-2xl"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4" style={{ borderColor: "var(--line-soft)" }}>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
                Gestión de cuentas
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
                {mode === "create" ? "Nuevo usuario" : `Editar ${user?.username}`}
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph-fill ph-x" style={{ fontSize: "15px" }} />
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
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
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
                className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
                style={fieldStyle}
              />
            </div>

            <div>
              <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Correo</label>
              <input
                type="email"
                value={email ?? ""}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
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
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium"
                  style={fieldStyle}
                />
              </div>
            )}

            <div>
              <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Rol</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={rolesLoading || roles.length === 0}
                className="w-full px-3 py-2 rounded-lg text-[13px] outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent font-medium cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                style={fieldStyle}
              >
                {roles.length === 0 && (
                  <option value="">{rolesLoading ? "Cargando roles..." : "Sin roles disponibles"}</option>
                )}
                {roles.map((r) => (
                  <option key={r.id} value={r.name}>{r.name}</option>
                ))}
              </select>
              {rolesError && (
                <p className="text-[10.5px] mt-1" style={{ color: "var(--crit)" }}>{rolesError}</p>
              )}
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
              disabled={saving}
              className="px-4 py-2 rounded-lg text-[13px] font-bold cursor-pointer transition-premium btn-hover shadow-sm disabled:opacity-50"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 rounded-lg text-[13px] font-bold cursor-pointer border-0 transition-premium btn-hover shadow-sm disabled:opacity-50"
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
