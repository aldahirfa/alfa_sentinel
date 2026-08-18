import { createPortal } from "react-dom";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";
import FloatingAlertCard from "./FloatingAlertCard";

interface Props {
  onViewAlert: (id: number) => void;
  onViewIncident: (id: number) => void;
}

// Capa global de notificaciones flotantes de alta prioridad (ALTO/
// CRÍTICO) -- sección 7/13 de la especificación original de alertas
// flotantes (2026-08-17, ver PENDIENTES.md): "una sola fuente/proveedor
// global de eventos de alerta que alimenta toda la app", montada UNA
// vez en App.tsx, nunca por pantalla. Portal a #app-shell (mismo patrón
// que RuleEditModal.tsx y el resto de los modales -- ver comentario en
// App.tsx sobre por qué no puede ir a document.body directamente: las
// variables de tema [data-theme] se resuelven en #app-shell).
//
// Consume GlobalAlertsProvider (context/GlobalAlertsContext.tsx) en vez
// de tener su propio poll -- reescrito 2026-08-17 (ver PENDIENTES.md,
// "Corrección de tiempo real, ordenamiento y consistencia", sección
// 19): el poll ahora vive en el Provider, montado en App.tsx por
// encima de esta capa Y de las pantallas de Alertas/Incidentes, así
// todas comparten la MISMA fuente sin duplicar peticiones.
//
// z-[60]: el z-index más alto usado hasta ahora en el proyecto era
// z-[51] (EscalateAlertModal.tsx, un modal sobre otro modal) -- esta
// capa tiene que quedar por encima de absolutamente todo, incluidos
// drawers/modales abiertos, porque es justamente para que una alerta
// crítica nunca pase desapercibida sin importar qué esté haciendo el
// operador (sección 1).
export default function GlobalAlertsLayer({ onViewAlert, onViewIncident }: Props) {
  const { visible, dismiss } = useGlobalAlertsContext();

  const portalTarget = document.getElementById("app-shell") ?? document.body;

  if (visible.length === 0) return null;

  return createPortal(
    <div
      className="fixed z-[60] flex flex-col gap-2.5 items-end px-3 sm:px-0"
      style={{
        // Debajo del topbar, con separación clara de la campana de
        // notificaciones existente (sección 6).
        top: "76px",
        right: 0,
        left: 0,
        pointerEvents: "none",
      }}
    >
      {visible.map((item) => (
        <div key={item.key} style={{ pointerEvents: "auto" }} className="w-full sm:w-auto flex justify-end">
          <FloatingAlertCard
            item={item}
            onClose={() => dismiss(item.key)}
            onViewAlert={onViewAlert}
            onViewIncident={onViewIncident}
          />
        </div>
      ))}
    </div>,
    portalTarget,
  );
}
