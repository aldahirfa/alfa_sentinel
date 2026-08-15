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

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Usuarios y roles</h3>
        {isAdmin && (
          <button
            onClick={() => setModal({ mode: "create", user: null })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[12px] font-semibold border-0 cursor-pointer"
            style={{ background: "var(--brand)", color: "#fff" }}
          >
            <i className="ph ph-user-plus" style={{ fontSize: "13px" }} />
            Nuevo usuario
          </button>
        )}
      </div>

      {!isAdmin && (
        <p className="text-[11.5px] mb-3" style={{ color: "var(--tx-mute)" }}>
          Solo el rol <code>admin</code> puede crear o editar usuarios. Podés ver la lista, pero las acciones están deshabilitadas.
        </p>
      )}

      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Usuario</th>
            <th className="pb-2 pr-3 font-semibold">Correo</th>
            <th className="pb-2 pr-3 font-semibold">Rol</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Último acceso</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                {Array.from({ length: 6 }).map((_, j) => (
                  <td key={j} className="py-3 pr-3">
                    <div className="h-3.5 rounded animate-pulse" style={{ background: "var(--surf3)", width: "60%" }} />
                  </td>
                ))}
              </tr>
            ))
          ) : (
            users.map((u) => (
              <tr key={u.id} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
                <td className="py-2.5 pr-3">
                  <div className="font-semibold" style={{ color: "var(--tx)" }}>{u.full_name}</div>
                  <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>@{u.username}</div>
                </td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{u.email ?? "—"}</td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-dim)" }}>{u.roles ?? "—"}</td>
                <td className="py-2.5 pr-3">
                  <span
                    className="text-[10.5px] font-medium px-2 py-0.5 rounded inline-block"
                    style={u.is_active ? { background: "var(--ok-soft)", color: "var(--ok)" } : { border: "1px solid var(--line)", color: "var(--tx-mute)" }}
                  >
                    {u.is_active ? "Activo" : "Desactivado"}
                  </span>
                </td>
                <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>{u.last_login_at ?? "Nunca"}</td>
                <td className="py-2.5">
                  {isAdmin && (
                    <button
                      onClick={() => setModal({ mode: "edit", user: u })}
                      className="flex items-center gap-1 text-[11.5px] font-medium border-0 bg-transparent cursor-pointer whitespace-nowrap"
                      style={{ color: "var(--brand)" }}
                    >
                      Editar
                      <i className="ph ph-pencil-simple text-[12px]" />
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {modal && (
        <UserFormModal
          mode={modal.mode}
          user={modal.user}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null);
            onChanged();
          }}
        />
      )}
    </section>
  );
}
