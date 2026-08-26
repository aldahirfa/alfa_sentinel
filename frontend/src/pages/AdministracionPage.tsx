import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
import AdminTabs from "../components/AdminTabs";
import type { AdminTab } from "../components/AdminTabs";
import UsersPanel from "../components/UsersPanel";
import AgentsPanel from "../components/AgentsPanel";
import ConfigPanel from "../components/ConfigPanel";
import AuditLogPanel from "../components/AuditLogPanel";
import { fetchAgentSettings, fetchAuditLogs, fetchUsers } from "../api/client";
import type { AuditLogsResponse, UsersResponse } from "../types/admin";

interface Props {
  isAdmin: boolean;
}

const TAB_META: Record<AdminTab, { eyebrow: string; title: string; description: string }> = {
  usuarios: { eyebrow: "Control de acceso", title: "Usuarios y roles", description: "Administra cuentas, permisos y estado de acceso a la consola central." },
  agentes: { eyebrow: "Enrolamiento", title: "Alta de nuevos agentes", description: "Genera credenciales temporales para registrar endpoints nuevos de forma controlada." },
  configuracion: { eyebrow: "Parámetros del sistema", title: "Configuración operacional", description: "Ajusta valores que afectan la interpretación del estado de los agentes y la consola." },
  auditoria: { eyebrow: "Trazabilidad", title: "Registro de actividad", description: "Consulta acciones administrativas y eventos relevantes realizados dentro del sistema." },
};

export default function AdministracionPage({ isAdmin }: Props) {
  const [tab, setTab] = useState<AdminTab>("usuarios");
  const [usersData, setUsersData] = useState<UsersResponse | null>(null);
  const [usersLoading, setUsersLoading] = useState(true);
  const [agentStaleSeconds, setAgentStaleSeconds] = useState<number | null>(null);
  const [auditPage, setAuditPage] = useState(1);
  const [auditData, setAuditData] = useState<AuditLogsResponse | null>(null);
  const [auditLoading, setAuditLoading] = useState(true);

  function loadUsers() {
    setUsersLoading(true);
    fetchUsers().then(setUsersData).finally(() => setUsersLoading(false));
  }

  useEffect(() => {
    loadUsers();
    fetchAgentSettings().then((res) => setAgentStaleSeconds(res.agent_stale_seconds));
  }, []);

  useEffect(() => {
    setAuditLoading(true);
    fetchAuditLogs(auditPage).then(setAuditData).finally(() => setAuditLoading(false));
  }, [auditPage]);

  const meta = TAB_META[tab];

  return (
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-8">
      <ModuleIntro
        page="administracion"
        eyebrow="Gestión del sistema"
        title="Administración central"
        description="Gestiona accesos, enrolamiento de agentes, parámetros operativos y trazabilidad administrativa desde un único espacio."
        trailing={(
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl border text-[9.5px]" style={{ background: isAdmin ? "var(--brand-fill)" : "var(--surf2)", borderColor: isAdmin ? "var(--brand-soft)" : "var(--line-soft)", color: isAdmin ? "var(--brand)" : "var(--tx-mute)" }}>
            <i className={isAdmin ? "ph ph-shield-check" : "ph ph-eye"} />
            {isAdmin ? "Permisos administrativos" : "Acceso de solo lectura"}
          </div>
        )}
      />

      <AdminTabs tab={tab} onChange={setTab} />

      <div className="module-subsection px-1 pt-1">
        <div className="text-[9px] font-bold tracking-[.14em] uppercase" style={{ color: "var(--brand)" }}>{meta.eyebrow}</div>
        <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>{meta.title}</div>
        <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{meta.description}</div>
      </div>

      {tab === "usuarios" && <UsersPanel users={usersData?.users ?? []} isAdmin={usersData?.is_admin ?? isAdmin} loading={usersLoading} onChanged={loadUsers} />}
      {tab === "agentes" && <AgentsPanel isAdmin={isAdmin} />}
      {tab === "configuracion" && (agentStaleSeconds !== null ? <ConfigPanel agentStaleSeconds={agentStaleSeconds} onChanged={setAgentStaleSeconds} /> : <div className="h-[250px] rounded-2xl animate-pulse" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }} />)}
      {tab === "auditoria" && <AuditLogPanel entries={auditData?.entries ?? []} loading={auditLoading} page={auditData?.page ?? 1} totalPages={auditData?.total_pages ?? 1} total={auditData?.total ?? 0} onPageChange={setAuditPage} />}
    </main>
  );
}
