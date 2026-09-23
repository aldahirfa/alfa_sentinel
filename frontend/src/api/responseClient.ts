import type {
  ResponseEndpointDetail,
  ResponseEndpointsResponse,
} from "../types/respuesta";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Error ${res.status} al pedir ${path}`);
  }
  return res.json() as Promise<T>;
}

export function fetchResponseEndpoints(): Promise<ResponseEndpointsResponse> {
  return request<ResponseEndpointsResponse>("/api/respuesta/endpoints");
}

export function fetchResponseEndpointDetail(agentId: number): Promise<ResponseEndpointDetail> {
  return request<ResponseEndpointDetail>(`/api/respuesta/endpoints/${agentId}`);
}
