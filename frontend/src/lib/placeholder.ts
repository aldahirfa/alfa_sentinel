// Convención de dato de prueba, a pedido explícito (2026-08-15):
// donde el backend todavía no tiene forma de obtener un dato real
// (no es un cero real, es una ausencia estructural -- ver
// PENDIENTES.md), se muestra un valor obviamente falso en vez de
// inventar algo creíble: "99" para números, "aquí va el dato" para
// texto. Así se distingue a simple vista de un dato real.
//
// OJO: esto NO aplica a valores que sí son reales y honestamente
// cero o null por otra razón (ej. endpoints_isolated=0 es un cero
// real -- nada está aislado hoy -- no un dato faltante).

export const PLACEHOLDER_NUMBER = 99;
export const PLACEHOLDER_TEXT = "aquí va el dato";

export function numOrPlaceholder(value: number | null | undefined): number {
  return value === null || value === undefined ? PLACEHOLDER_NUMBER : value;
}

export function textOrPlaceholder(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? PLACEHOLDER_TEXT : value;
}

// Para resaltar visualmente que es un dato de prueba (no lo pide el
// mockup original, pero ayuda a no confundirlo con un dato real
// mientras se ve en pantalla).
export function isPlaceholderNumber(value: number): boolean {
  return value === PLACEHOLDER_NUMBER;
}
