export type Page = "dashboard" | "endpoints" | "alerts" | "incidentes" | "honeyfiles" | "reglas" | "respuesta" | "reportes" | "administracion" | "perfil";

export function ModuleMark({ page, size = 17 }: { page: Page; size?: number }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.65,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      {page === "dashboard" && (
        <>
          <path {...common} d="M4.25 5.25h6.2v5.5h-6.2zM13.55 5.25h6.2v3.35h-6.2zM13.55 11.7h6.2v7.05h-6.2zM4.25 13.7h6.2v5.05h-6.2z" />
          <circle cx="17.7" cy="7" r=".85" fill="currentColor" />
        </>
      )}
      {page === "endpoints" && (
        <>
          <rect {...common} x="3.5" y="4.5" width="17" height="11.5" rx="2.2" />
          <path {...common} d="M8.2 19.5h7.6M12 16v3.5" />
          <circle cx="17.1" cy="8.3" r="1.15" fill="currentColor" />
        </>
      )}
      {page === "alerts" && (
        <>
          <path {...common} d="M10.2 4.25 3.7 17.05a1.85 1.85 0 0 0 1.65 2.7h13.3a1.85 1.85 0 0 0 1.65-2.7L13.8 4.25a2 2 0 0 0-3.6 0Z" />
          <path {...common} d="M12 8.2v5.15" />
          <circle cx="12" cy="16.65" r="1" fill="currentColor" />
        </>
      )}
      {page === "incidentes" && (
        <>
          <path {...common} d="m12 3.35 7.25 4.2v8.9L12 20.65l-7.25-4.2v-8.9z" />
          <circle {...common} cx="12" cy="12" r="3.25" />
          <path {...common} d="M12 6.8v1.9M12 15.3v1.9M6.8 12h1.9M15.3 12h1.9" />
        </>
      )}
      {page === "honeyfiles" && (
        <>
          <path {...common} d="M6 3.7h7l5 5v11.6H6z" />
          <path {...common} d="M13 3.7v5h5" />
          <circle {...common} cx="11.2" cy="14.1" r="2.35" />
          <path {...common} d="m12.9 15.8 2.05 2.05" />
        </>
      )}
      {page === "reglas" && (
        <>
          <path {...common} d="M5 6h14M5 12h14M5 18h14" />
          <circle cx="9" cy="6" r="1.65" fill="currentColor" fillOpacity=".08" stroke="currentColor" strokeWidth="1.65" />
          <circle cx="15" cy="12" r="1.65" fill="currentColor" fillOpacity=".08" stroke="currentColor" strokeWidth="1.65" />
          <circle cx="11" cy="18" r="1.65" fill="currentColor" fillOpacity=".08" stroke="currentColor" strokeWidth="1.65" />
        </>
      )}
      {page === "respuesta" && (
        <>
          <path {...common} d="M12 3.35c2.35 1.75 4.9 2.25 7.15 2.55v5.55c0 4.05-2.45 7.35-7.15 9.2-4.7-1.85-7.15-5.15-7.15-9.2V5.9C7.1 5.6 9.65 5.1 12 3.35Z" />
          <path {...common} d="m13.15 7.7-3.4 4.75h2.65l-1.15 3.85 3.45-5h-2.65z" />
        </>
      )}
      {page === "reportes" && (
        <>
          <path {...common} d="M5.2 3.75h9.1l4.5 4.5v12H5.2z" />
          <path {...common} d="M14.3 3.75v4.5h4.5M8.3 16.7v-2.4M11.5 16.7v-4.9M14.7 16.7v-7" />
        </>
      )}
      {page === "administracion" && (
        <>
          <path {...common} d="M12 3.4 19.1 7.5v8.2L12 19.8l-7.1-4.1V7.5z" />
          <circle {...common} cx="12" cy="11.6" r="2.55" />
          <path {...common} d="M8.1 17.25c.65-1.6 2.05-2.55 3.9-2.55s3.25.95 3.9 2.55" />
        </>
      )}
      {page === "perfil" && (
        <>
          <circle {...common} cx="12" cy="8.35" r="3.15" />
          <path {...common} d="M5.8 19.4c.7-3.55 2.85-5.55 6.2-5.55s5.5 2 6.2 5.55" />
          <path {...common} d="M4.1 12V6.1A2.1 2.1 0 0 1 6.2 4h1.1M19.9 12V6.1A2.1 2.1 0 0 0 17.8 4h-1.1" />
        </>
      )}
    </svg>
  );
}
