import type { CSSProperties } from "react";
import type { HoneyfileStatus } from "../types/honeyfiles";

// Mismo patrón ya usado en lib/endpointStatus.ts para
// ONLINE/OFFLINE/ISOLATED: un estado binario bueno/malo real (un
// honeyfile activado es, en los hechos, un compromiso confirmado)
// reusa los extremos de la escala --ok/--crit en vez de inventar un
// quinto color -- 'TRIGGERED' no es un nivel de severidad de
// 'severity_levels', pero visualmente es tan grave como CRITICAL.

export const HONEYFILE_STATUS_LABEL: Record<HoneyfileStatus, string> = {
  ACTIVE: "Activo (intacto)",
  TRIGGERED: "Activado / comprometido",
  INACTIVE: "Inactivo",
};

export const HONEYFILE_STATUS_VAR: Record<HoneyfileStatus, string> = {
  ACTIVE: "var(--ok)",
  TRIGGERED: "var(--crit)",
  INACTIVE: "var(--off)",
};

export function honeyfileStatusPillStyle(status: HoneyfileStatus): CSSProperties {
  if (status === "TRIGGERED") {
    return { background: "var(--crit)", color: "#fff" };
  }
  if (status === "ACTIVE") {
    return { background: "var(--ok-soft)", color: "var(--ok)" };
  }
  return { border: "1px solid var(--line)", color: "var(--tx-mute)" };
}

// Ubicaciones LÓGICAS de un señuelo (honeyfile_templates.file_path); el
// agente las resuelve a la carpeta real según su SO (agent/paths.py).
export const HONEYFILE_LOCATION_LABEL: Record<string, string> = {
  DOCUMENTS: "Documentos",
  DESKTOP: "Escritorio",
  DOWNLOADS: "Descargas",
  PICTURES: "Imágenes",
};

export const HONEYFILE_PLATFORM_LABEL: Record<string, string> = {
  WINDOWS: "Windows",
  LINUX: "Linux",
  ALL: "Windows y Linux",
};

export function fileTypeIcon(fileType: string): string {
  const t = fileType.toUpperCase();
  if (["XLSX", "XLS", "CSV"].includes(t)) return "ph-fill ph-file-xls";
  if (["ZIP", "RAR", "7Z", "TAR"].includes(t)) return "ph-fill ph-file-zip";
  if (["DOCX", "DOC"].includes(t)) return "ph-fill ph-file-doc";
  if (t === "PDF") return "ph-fill ph-file-pdf";
  return "ph ph-file-text";
}
