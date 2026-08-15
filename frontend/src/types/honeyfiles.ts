// Tipos alineados 1:1 con GET /api/honeyfiles, GET /api/honeyfiles/{id}/detail,
// POST /api/honeyfiles/{id}/toggle-status y POST /api/honeyfiles/deploy
// (server/main.py) -- los 3 últimos ya existían y los usaba
// honeyfiles.html; el primero es la versión JSON nueva de esa misma
// pantalla para React.

// 'TRIGGERED' no es un valor real de honeyfiles.status en la base
// (que solo guarda ACTIVE/INACTIVE) -- es un estado calculado en el
// servidor cuando un honeyfile ACTIVE tiene activaciones registradas.
export type HoneyfileStatus = "ACTIVE" | "INACTIVE" | "TRIGGERED";

export interface HoneyfileListItem {
  id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  status: HoneyfileStatus;
  created_at: string | null;
  last_checked_at: string | null;
  agent_id: number;
  hostname: string;
  ip_address: string;
  operating_system: string;
  os_version: string;
  agent_version: string;
  agent_status: string;
  is_agent_live: boolean;
  activations_count: number;
}

export interface HoneyfilesSummary {
  total: number;
  active: number;
  triggered: number;
  pending_deployments: number;
  failed_deployments: number;
}

export interface AvailableAgent {
  id: number;
  hostname: string;
  operating_system: string;
  os_version: string;
  ip_address: string;
  status: string;
  is_live: boolean;
}

export interface HoneyfilesResponse {
  summary: HoneyfilesSummary;
  distinct_os: string[];
  available_agents: AvailableAgent[];
  filtered_total: number;
  honeyfiles: HoneyfileListItem[];
}

export interface HoneyfilesQuery {
  search?: string;
  status?: HoneyfileStatus | "";
  os?: string;
  agent_id?: number;
}

export interface HoneyfileActivation {
  detected_at: string;
  operation: string;
  process_name: string;
  process_id: number;
}

export interface HoneyfileDetail {
  id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  sha256_hash: string;
  status: HoneyfileStatus;
  created_at: string;
  last_checked_at: string;
  agent_id: number;
  agent_code: string;
  hostname: string;
  ip_address: string;
  operating_system: string;
  os_version: string;
  agent_version: string;
  is_online: boolean;
  activations: HoneyfileActivation[];
  activations_count: number;
}

export interface DeployHoneyfilePayload {
  file_name: string;
  file_type: string;
  target_path: string;
  platform: "windows" | "linux" | "all";
  auto_deploy: boolean;
  content: string;
  agent_ids: number[];
}

export interface DeployHoneyfileResult {
  success: boolean;
  template_id: number;
  assigned_count: number;
  message: string;
}
