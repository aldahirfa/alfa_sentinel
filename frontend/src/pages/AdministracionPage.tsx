import { useEffect, useState } from "react";
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
    fetchUsers()
      .then(setUsersData)
      .finally(() => setUsersLoading(false));
  }

  useEffect(() => {
    loadUsers();
    fetchAgentSettings().then((res) => setAgentStaleSeconds(res.agent_stale_seconds));
  }, []);

  useEffect(() => {
    setAuditLoading(true);
    fetchAuditLogs(auditPage)
      .then(setAuditData)
      .finally(() => setAuditLoading(false));
  }, [auditPage]);

  return (
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8">
      <AdminTabs tab={tab} onChange={setTab} />

      {tab === "usuarios" && (
        <UsersPanel
          users={usersData?.users ?? []}
          isAdmin={usersData?.is_admin ?? isAdmin}
          loading={usersLoading}
          onChanged={loadUsers}
        />
      )}

      {tab === "agentes" && <AgentsPanel isAdmin={isAdmin} />}

      {tab === "configuracion" &&
        (agentStaleSeconds !== null ? (
          <ConfigPanel agentStaleSeconds={agentStaleSeconds} onChanged={setAgentStaleSeconds} />
        ) : (
          <div className="h-[220px] rounded-[10px] animate-pulse" style={{ background: "var(--surf2)" }} />
        ))}

      {tab === "auditoria" && (
        <AuditLogPanel
          entries={auditData?.entries ?? []}
          loading={auditLoading}
          page={auditData?.page ?? 1}
          totalPages={auditData?.total_pages ?? 1}
          total={auditData?.total ?? 0}
          onPageChange={setAuditPage}
        />
      )}
    </main>
  );
}
