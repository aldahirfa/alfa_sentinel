import type { CSSProperties } from "react";
import type { IncidentClassification, IncidentStatus, StatusBucket } from "../types/incidentes";

// Estos dos vocabularios (IncidentStatus/IncidentClassification) son
// copia directa de INCIDENT_STATUS_LABELS_ES / INCIDENT_CLASSIFICATION_LABELS_ES
// en server/main.py -- no hay endpoint que los liste dinámicamente
// porque son valores fijos del propio código del servidor, igual que
// ALERT_STATUS_LABELS_ES en lib/alertStatus.ts.

export const INCIDENT_STATUS_LABEL: Record<IncidentStatus, string> = {
  OPEN: "Abierto",
  IN_PROGRESS: "En investigación",
  CONTAINED: "Contenido",
  CLOSED: "Cerrado",
};

export const INCIDENT_CLASSIFICATION_LABEL: Record<IncidentClassification, string> = {
  CONFIRMED: "Confirmado",
  POSSIBLE_THREAT: "Posible amenaza",
  FALSE_POSITIVE: "Falso positivo",
  LEGITIMATE_ACTIVITY: "Actividad legítima",
  UNDETERMINED: "No determinado",
};

// status_bucket unifica incidents.status y alerts.status en un solo
// eje visual (ver STATUS_BUCKET_LABELS_ES en el servidor) -- es un
// estado de flujo de trabajo, no de severidad, así que usa la misma
// escala neutral/informativa que lib/alertStatus.ts, nunca los 4
// colores de riesgo.
export const STATUS_BUCKET_VAR: Record<StatusBucket, string> = {
  nuevo: "var(--info)",
  investigando: "var(--info)",
  confirmado: "var(--brand)",
  contenido: "var(--brand)",
  cerrado: "var(--off)",
  falso_positivo: "var(--off)",
};

export function statusBucketPillStyle(bucket: StatusBucket): CSSProperties {
  if (bucket === "nuevo") {
    return { background: "var(--info-soft)", color: "var(--info)" };
  }
  if (bucket === "confirmado" || bucket === "contenido") {
    return { background: "var(--brand-soft)", color: "var(--brand)" };
  }
  if (bucket === "investigando") {
    return { border: "1px solid var(--info)", color: "var(--info)" };
  }
  return { border: "1px solid var(--line)", color: "var(--tx-mute)" };
}
