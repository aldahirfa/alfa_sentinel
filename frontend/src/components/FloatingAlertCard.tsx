import type { FloatingAlert } from "../context/GlobalAlertsContext";
import { SEVERITY_VAR, SEVERITY_SOFT_VAR } from "../lib/severity";

interface Props {
  item: FloatingAlert;
  onClose: () => void;
  onViewAlert: (id: number) => void;
  onViewIncident: (id: number) => void;
}

// Etiquetas cortas para la línea de aislamiento -- sección 23 de la
// especificación "Alertas flotantes globales de alta prioridad"
// (2026-08-17, ver PENDIENTES.md): "mostrar el resultado REAL... NO
// mostrar 'RECOMMENDED' si el sistema ya ejecutó el aislamiento".
// Versión compacta de ISOLATION_STATUS_LABELS_ES (server/main.py) --
// acá interesa una palabra reconocible en una tarjeta chica, no la
// frase completa que sí tiene sentido en la tabla de /respuesta.
const ISOLATION_SHORT_LABEL: Record<string, string> = {
  REQUESTED: "En ejecución",
  EXECUTED: "Aislado",
  ISOLATION_FAILED: "Falló",
  RECOMMENDED: "Recomendado",
  RELEASE_REQUESTED: "Liberando",
  RELEASED: "Liberado",
};

// Mismos colores que IncidentesTable.tsx/CriticalIncidentsTable.tsx/
// IncidentDrawer.tsx para el mismo campo real 'isolation_status' --
// sección 18 de "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO REAL..."
// (2026-08-17, ver PENDIENTES.md): un mismo estado debe verse igual
// en todas las pantallas, incluida la notificación flotante.
function isolationColor(status: string): string {
  if (status === "EXECUTED") return "var(--crit)";
  if (status === "REQUESTED" || status === "RELEASE_REQUESTED") return "var(--warn)";
  if (status === "ISOLATION_FAILED") return "var(--warn)";
  return "var(--tx-mute)";
}

export default function FloatingAlertCard({ item, onClose, onViewAlert, onViewIncident }: Props) {
  const isCritico = item.severity === "CRÍTICO";
  const icon = isCritico ? "ph-siren" : "ph-warning";
  const isolationLabel = item.isolation_status ? ISOLATION_SHORT_LABEL[item.isolation_status] : null;

  return (
    <div
      role="alert"
      className="w-full sm:w-[360px] rounded-xl border overflow-hidden shadow-2xl animate-[alfaFloatIn_.22s_ease-out]"
      style={{
        background: "var(--surf)",
        borderColor: isCritico ? "var(--crit)" : "var(--high)",
        borderLeftWidth: "4px",
      }}
    >
      <div className="flex items-start gap-2.5 px-4 pt-3.5 pb-3">
        <div
          className="w-8 h-8 rounded-lg grid place-items-center shrink-0"
          style={{ background: isCritico ? "var(--crit)" : SEVERITY_SOFT_VAR.ALTO, color: isCritico ? "#fff" : SEVERITY_VAR.ALTO }}
        >
          <i className={`ph-fill ${icon}`} style={{ fontSize: isCritico ? "17px" : "15px" }} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className="text-[10px] font-bold tracking-wider px-1.5 py-0.5 rounded"
              style={isCritico ? { background: "var(--crit)", color: "#fff" } : { background: SEVERITY_SOFT_VAR.ALTO, color: SEVERITY_VAR.ALTO }}
            >
              {item.severity}
            </span>
            <span className="text-[10.5px] font-medium ml-auto shrink-0" style={{ color: "var(--tx-mute)" }}>
              {item.created_at}
            </span>
          </div>

          <div className="text-[13px] font-bold mt-1.5 leading-tight" style={{ color: "var(--tx)" }}>
            {item.title}
          </div>

          <div className="flex items-center gap-1.5 mt-1 text-[11.5px]" style={{ color: "var(--tx-dim)" }}>
            <i className="ph ph-desktop-tower" style={{ fontSize: "12px" }} />
            <span className="truncate">{item.hostname}</span>
            <span style={{ color: "var(--tx-mute)" }}>·</span>
            <span>Score {Math.round(item.risk_score)}</span>
          </div>

          {isolationLabel && (
            <div className="flex items-center gap-1.5 mt-1.5 text-[11px] font-semibold" style={{ color: isolationColor(item.isolation_status!) }}>
              <i className="ph-fill ph-plugs" style={{ fontSize: "12px" }} />
              Aislamiento: {isolationLabel}
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          aria-label="Cerrar notificación"
          title="Cerrar"
          className="shrink-0 w-6 h-6 rounded-md grid place-items-center cursor-pointer border-0 bg-transparent transition-colors hover:bg-[var(--surf2)]"
          style={{ color: "var(--tx-mute)" }}
        >
          <i className="ph ph-x" style={{ fontSize: "13px" }} />
        </button>
      </div>

      <div className="flex border-t" style={{ borderColor: "var(--line-soft)" }}>
        {item.incident_id ? (
          <button
            onClick={() => onViewIncident(item.incident_id!)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[12px] font-bold cursor-pointer border-0 bg-transparent transition-colors hover:bg-[var(--surf2)]"
            style={{ color: "var(--brand)" }}
          >
            Ver incidente
            <i className="ph-fill ph-arrow-right" style={{ fontSize: "12px" }} />
          </button>
        ) : (
          <button
            onClick={() => onViewAlert(item.id)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[12px] font-bold cursor-pointer border-0 bg-transparent transition-colors hover:bg-[var(--surf2)]"
            style={{ color: "var(--brand)" }}
          >
            Ver alerta
            <i className="ph-fill ph-arrow-right" style={{ fontSize: "12px" }} />
          </button>
        )}
      </div>
    </div>
  );
}
