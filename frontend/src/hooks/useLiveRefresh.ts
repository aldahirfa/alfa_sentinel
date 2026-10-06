import { useEffect, useRef, useState } from "react";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

// Cada cuánto se recarga, en segundo plano, la pantalla que se está mirando.
export const LIVE_REFRESH_MS = 5_000;

// Actualización en vivo de la consola (2026-10-06): antes, salvo el panel
// de control y la campana, cada pantalla pedía sus datos una sola vez y
// había que recargar el navegador para ver un cambio (estado o puntaje de
// una alerta, un incidente, un equipo que se desconecta...).
//
// Devuelve un número que cambia cada vez que la pantalla debe volver a
// pedir sus datos, SIN mostrar el estado de "cargando":
//  - cada LIVE_REFRESH_MS, solo mientras la pantalla está a la vista
//    ('active') y la pestaña del navegador está visible;
//  - al volver a esta pantalla o a la pestaña;
//  - en cuanto el poll global de alertas (GlobalAlertsContext, cada 3 s)
//    detecta un cambio, aunque la pantalla esté oculta.
// Vale 0 hasta el primer cambio: la carga inicial la hace cada pantalla.
export function useLiveRefresh(active: boolean): number {
  const { refreshToken } = useGlobalAlertsContext();
  const [tick, setTick] = useState(0);
  const mounted = useRef(false);

  useEffect(() => {
    if (mounted.current) setTick((t) => t + 1);
  }, [refreshToken]);

  useEffect(() => {
    if (!active) return;
    const bump = () => {
      if (document.visibilityState === "visible") setTick((t) => t + 1);
    };
    if (mounted.current) bump();
    const id = setInterval(bump, LIVE_REFRESH_MS);
    document.addEventListener("visibilitychange", bump);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", bump);
    };
  }, [active]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  return tick;
}
