// Tipos alineados 1:1 con server/main.py::api_perfil (GET /api/perfil),
// versión JSON de la misma consulta que ya usaba perfil_page (Jinja2).

export interface ProfileResponse {
  username: string;
  full_name: string;
  email: string | null;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
  roles: string[];
}

export interface ProfileUpdatePayload {
  full_name: string;
  email: string | null;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}
