// Celda de fecha de las tablas. Un solo estilo para toda la consola:
// tamaño de la tabla, color tenue, cifras alineadas y sin salto de línea.
// El texto ya llega formateado del servidor (dd/mm/aaaa HH:MM:SS).

export default function DateCell({ value, className = "px-3 py-3.5" }: { value: string | null | undefined; className?: string }) {
  return (
    <td className={`${className} whitespace-nowrap tabular-nums`} style={{ color: "var(--tx-mute)" }}>
      {value || "—"}
    </td>
  );
}
