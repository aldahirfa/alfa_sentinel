import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { fetchOpenAlerts } from "../api/client";
import type { OpenAlert } from "../api/client";
import { playAlertSound } from "../lib/notificationSound";

// Proveedor global único de alertas (2026-08-17, ver PENDIENTES.md,
// "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO REAL, ORDENAMIENTO Y
// CONSISTENCIA DE ALERTAS, INCIDENTES Y AISLAMIENTO", sección 19:
// "Backend -> estado real -> Global Alerts/Incidents Provider -> UI").
// Reemplaza el hook `useGlobalAlerts` anterior (vivía dentro de
// GlobalAlertsLayer, sección 29 de la especificación previa de
// "Alertas flotantes globales") -- ese diseño encerraba el ÚNICO poll
// dentro de un componente hijo de App.tsx, así que ninguna otra
// pantalla (Alertas, Incidentes) podía enterarse de un cambio nuevo sin
// arrancar SU PROPIO poll independiente. Acá el poll vive en un
// Context.Provider montado en la raíz (App.tsx), y cualquier
// componente lo consume vía useGlobalAlertsContext() -- un solo
// intervalo, cero peticiones duplicadas.
//
// Medido antes de tocar nada (sección 25): GET /alerts/open responde en
// ~15ms incluso con cientos de alertas ya en la base -- el backend
// nunca fue el cuello de botella. La demora percibida venía de (a) un
// intervalo de poll conservador y, sobre todo, (b) que AlertsPage/
// IncidentesPage no tenían NINGÚN mecanismo de actualización automática
// -- cargaban una vez al entrar a la pantalla y no volvían a pedir nada
// hasta que el usuario cambiaba un filtro. Ver PENDIENTES.md para el
// detalle completo de la auditoría y la corrección.
const POLL_INTERVAL_MS = 3_000;

// Sección 26 (heredada de la especificación de alertas flotantes, sigue
// vigente): como máximo unas pocas tarjetas visibles a la vez.
const MAX_VISIBLE = 4;

const FLOATING_SEVERITIES = new Set(["ALTO", "CRÍTICO"]);
const SEVERITY_RANK: Record<string, number> = { BAJO: 0, MEDIO: 1, ALTO: 2, CRÍTICO: 3 };

export interface FloatingAlert extends OpenAlert {
  // Identificador de instancia de la notificación (no de la alerta):
  // una escalada ALTO->CRÍTICO de la MISMA alerta genera una fila
  // nueva en la cola, aunque comparta alert.id.
  key: string;
}

// Snapshot mínimo por alerta para decidir "¿cambió algo relevante desde
// el último poll?" (sección 4/9: escalada de severidad SÍ importa,
// CRÍTICO->CRÍTICO sin cambio NO; sección 21/22: un incidente
// nuevo/actualizado o un cambio de estado de aislamiento también deben
// disparar un refresco de las tablas, aunque no floten).
interface AlertSnapshot {
  severity: string;
  incident_id: number | null;
  isolation_status: string | null;
}

interface GlobalAlertsContextValue {
  visible: FloatingAlert[];
  // Cerrar es SIEMPRE manual (sección 2 de la especificación de tiempo
  // real: "no debe desaparecer automáticamente... hasta que el usuario
  // pulse Cerrar") -- nunca borra/reconoce/cambia el estado real de la
  // alerta, solo la quita de esta lista en memoria.
  dismiss: (key: string) => void;
  // Se incrementa cada vez que el poll detecta un cambio real (alerta
  // nueva, escalada, incidente nuevo/asociado, cambio de estado de
  // aislamiento). AlertsPage/IncidentesPage lo agregan como dependencia
  // de su propio efecto de carga -- reaccionan a la MISMA señal de un
  // solo poll, nunca arrancan un poll propio (sección 19).
  refreshToken: number;
  // Total de alertas NEW (campo 'count' de /alerts/open, ya lo trae
  // cada poll de 3s -- sin pedir nada de más). Corregido 2026-08-18
  // (ver PENDIENTES.md, "Corrección definitiva en la lógica y
  // presentación de ALERTAS", sección 13): el contador de la campana
  // (Topbar/NotificationsBell) usaba 'summary.alerts_active' del poll
  // de /api/dashboard/overview, que tiene SU PROPIO intervalo de 20s
  // -- un ciclo de actualización totalmente aparte del de esta misma
  // capa, justo el patrón de "polling independiente por pantalla/
  // widget" que la sección 19 de la especificación anterior pedía
  // evitar. Como consecuencia, la campana podía tardar hasta 20s en
  // reflejar una alerta que la ventana flotante y las tablas de
  // Alertas/Incidentes ya mostraban hace segundos. Se expone acá para
  // que la campana lea la MISMA fuente de 3s, sin arrancar un poll
  // propio.
  openAlertsCount: number;
}

const GlobalAlertsContext = createContext<GlobalAlertsContextValue | null>(null);

export function GlobalAlertsProvider({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState<FloatingAlert[]>([]);
  const [refreshToken, setRefreshToken] = useState(0);
  const [openAlertsCount, setOpenAlertsCount] = useState(0);
  const queueRef = useRef<FloatingAlert[]>([]);
  // alert_id -> último snapshot conocido (identidad SIEMPRE por
  // alert_id, nunca por título+hora).
  const seenRef = useRef<Map<number, AlertSnapshot>>(new Map());
  // Primer poll = establecer una base sin notificar/refrescar nada --
  // abrir/recargar la consola no debe hacer flashear de golpe todo lo
  // que ya existía, solo lo que cambia DESPUÉS de tener una base real.
  const baselineSetRef = useRef(false);

  const dismiss = useCallback((key: string) => {
    setVisible((current) => {
      const next = current.filter((item) => item.key !== key);
      const promoted = queueRef.current.shift();
      return promoted ? [...next, promoted] : next;
    });
  }, []);

  const enqueue = useCallback((item: FloatingAlert) => {
    setVisible((current) => {
      if (current.length < MAX_VISIBLE) {
        return [...current, item];
      }
      queueRef.current.push(item);
      return current;
    });
  }, []);

  const poll = useCallback(async () => {
    let data;
    try {
      data = await fetchOpenAlerts();
    } catch {
      return; // un fallo puntual de red no debe tumbar el polling
    }

    setOpenAlertsCount(data.count);

    const isBaseline = !baselineSetRef.current;
    baselineSetRef.current = true;
    let anyChange = false;

    for (const alert of data.alerts) {
      const prev = seenRef.current.get(alert.id);
      const next: AlertSnapshot = {
        severity: alert.severity,
        incident_id: alert.incident_id,
        isolation_status: alert.isolation_status,
      };

      const isNew = prev === undefined;
      const severityChanged = !isNew && prev.severity !== next.severity;
      const incidentChanged = !isNew && prev.incident_id !== next.incident_id;
      const isolationChanged = !isNew && prev.isolation_status !== next.isolation_status;

      seenRef.current.set(alert.id, next);

      if (isBaseline) continue; // sin flash/refresco inicial de lo que ya existía

      if (isNew || severityChanged || incidentChanged || isolationChanged) {
        anyChange = true;
      }

      if (!FLOATING_SEVERITIES.has(alert.severity)) continue;

      const isEscalation = !isNew && SEVERITY_RANK[next.severity] > SEVERITY_RANK[prev.severity];
      if (!isNew && !isEscalation) continue; // ni nueva ni escalada -> no duplicar la flotante

      const item: FloatingAlert = { ...alert, key: `${alert.id}:${alert.severity}:${Date.now()}` };
      playAlertSound(alert.severity as "ALTO" | "CRÍTICO");
      enqueue(item);
    }

    if (anyChange) setRefreshToken((t) => t + 1);
  }, [enqueue]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [poll]);

  return (
    <GlobalAlertsContext.Provider value={{ visible, dismiss, refreshToken, openAlertsCount }}>
      {children}
    </GlobalAlertsContext.Provider>
  );
}

export function useGlobalAlertsContext(): GlobalAlertsContextValue {
  const ctx = useContext(GlobalAlertsContext);
  if (!ctx) {
    throw new Error("useGlobalAlertsContext debe usarse dentro de <GlobalAlertsProvider>");
  }
  return ctx;
}
