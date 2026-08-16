import { useEffect, useState } from "react";

// Cuánto dura el resaltado "fuerte" de una fila recién abierta antes
// de desvanecerse (vía transición CSS en la propia tabla, no acá)
// hasta quedar solo con el indicador persistente y sutil (borde
// izquierdo) mientras el drawer siga abierto.
const FLASH_MS = 6500;

// Pequeño estado compartido por todas las tablas con drawer de
// detalle (Alertas, Incidentes, Endpoints, Honeyfiles): dado el id
// actualmente seleccionado (o `null` si no hay ninguno), devuelve el
// id que debe mostrar el resaltado fuerte "temporal" en este momento.
// Cada tabla compara sus filas contra `selectedId` (indicador
// persistente sutil, todo el tiempo que el drawer esté abierto) y
// contra este valor de retorno (resaltado fuerte, solo unos segundos
// después de seleccionar). `selectedId` puede ser un número o -- para
// Incidentes, que mezcla "incident"/"alert" -- una clave de texto ya
// combinada por quien llama (ver IncidentesPage.tsx).
export function useRowFlash<T>(selectedId: T | null): T | null {
  const [flashId, setFlashId] = useState<T | null>(null);

  useEffect(() => {
    if (selectedId === null) {
      setFlashId(null);
      return;
    }
    setFlashId(selectedId);
    const t = setTimeout(() => setFlashId(null), FLASH_MS);
    return () => clearTimeout(t);
  }, [selectedId]);

  return flashId;
}
