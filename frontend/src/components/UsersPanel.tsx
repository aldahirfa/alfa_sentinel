import { useState } from "react";
import type { AdminUser } from "../types/admin";
import UserFormModal from "./UserFormModal";

interface Props {
  users: AdminUser[];
  isAdmin: boolean;
  loading: boolean;
  onChanged: () => void;
}

export default function UsersPanel({ users, isAdmin, loading, onChanged }: Props) {
  const [modal, setModal] = useState<{ mode: "create" | "edit"; user: AdminUser | null } | null>(null);
  const activeUsers = users.filter((u) => u.is_active).length;

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-users-three" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Directorio de acceso</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Usuarios registrados</div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{activeUsers} activos · {users.length} totales</span>
          {isAdmin && (
            <button onClick={() => setModal({ mode: "create", user: null })} className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-semibold border-0 cursor-pointer transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff" }}>
              <i className="ph ph-user-plus" style={{ fontSize: "13px" }} />
              Nuevo usuario
            </button>
          )}
        </div>
      </div>

      {!isAdmin && (
        <div className="mx-4 mt-4 rounded-xl px-3.5 py-3 text-[10px] flex items-start gap-2.5" style={{ background: "var(--info-fill)", color: "var(--tx-dim)", border: "1px solid var(--info-soft)" }}>
          <i className="ph ph-info mt-0.5" style={{ color: "var(--info)" }} />
          <span>Tu cuenta puede consultar el directorio, pero la creación y edición de usuarios requiere permisos administrativos.</span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[860px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Usuario</th>
              <th className="px-3 py-3 font-semibold">Correo</th>
              <th className="px-3 py-3 font-semibold">Rol</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Último acceso</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-3 py-3.5"><div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: "62%" }} /></td>)}</tr>)
            ) : users.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>No hay usuarios registrados.</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="border-t transition-premium" style={{ borderColor: "var(--line-soft)" }} onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")} onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <td className="px-4 py-3.5 min-w-[220px]">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl grid place-items-center text-[11px] font-bold shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>{(u.full_name || u.username).slice(0, 1).toUpperCase()}</div>
                      <div><div className="font-semibold" style={{ color: "var(--tx)" }}>{u.full_name}</div><div className="mono-data text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>@{u.username}</div></div>
                    </div>
                  </td>
                  <td className="px-3 py-3.5" style={{ color: "var(--tx-dim)" }}>{u.email ?? "—"}</td>
                  <td className="px-3 py-3.5"><span className="inline-flex px-2 py-1 rounded-lg text-[9.5px]" style={{ background: "var(--brand-fill)", color: "var(--brand)", border: "1px solid var(--brand-soft)" }}>{u.roles ?? "Sin rol"}</span></td>
                  <td className="px-3 py-3.5"><span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[9.5px]" style={u.is_active ? { background: "var(--ok-soft)", color: "var(--ok)" } : { background: "var(--surf3)", color: "var(--tx-mute)" }}><span className="w-1.5 h-1.5 rounded-full" style={{ background: u.is_active ? "var(--ok)" : "var(--off)" }} />{u.is_active ? "Activo" : "Desactivado"}</span></td>
                  <td className="px-3 py-3.5" style={{ color: "var(--tx-mute)" }}>{u.last_login_at ?? "Nunca"}</td>
                  <td className="px-4 py-3.5 text-right">{isAdmin ? <button onClick={() => setModal({ mode: "edit", user: u })} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover" style={{ background: "var(--brand-fill)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-pencil-simple" /><span className="text-[10px] font-semibold">Editar usuario</span></button> : <span className="text-[9px]" style={{ color: "var(--tx-mute)" }}>Solo lectura</span>}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modal && <UserFormModal mode={modal.mode} user={modal.user} onClose={() => setModal(null)} onSaved={() => { setModal(null); onChanged(); }} />}
    </section>
  );
}
