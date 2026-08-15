// Tipos alineados 1:1 con GET /api/users, POST /users, PATCH /users/{id},
// GET /api/config/agentes, PATCH /settings/{key}, GET /api/audit-logs
// y POST /enrollment-tokens (server/main.py). Los 4 endpoints de
// escritura ya existían y los usaba usuarios.html/configuracion.html.

export interface AdminUser {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  roles: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface UsersResponse {
  is_admin: boolean;
  users: AdminUser[];
}

export interface UserCreatePayload {
  username: string;
  password: string;
  full_name: string;
  email?: string | null;
  role: string;
}

export interface UserUpdatePayload {
  full_name?: string;
  email?: string;
  is_active?: boolean;
  role?: string;
}

export interface AgentSettingsResponse {
  agent_stale_seconds: number;
}

export interface AuditLogEntry {
  created_at: string | null;
  user_name: string;
  action: string;
  action_label: string;
  entity_type: string | null;
  entity_id: number | null;
  description: string | null;
}

export interface AuditLogsResponse {
  entries: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface EnrollmentTokenResult {
  message: string;
  token: string;
  token_id: number;
  expires_at: string;
}
