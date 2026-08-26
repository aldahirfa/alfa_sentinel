import type { ReactNode } from "react";
import type { Page } from "./ModuleMark";

interface Props {
  page: Page;
  eyebrow: string;
  title: string;
  description: string;
  trailing?: ReactNode;
}

/**
 * El nombre y la descripción principal de cada módulo ya se muestran
 * en la Topbar. Mantener un segundo encabezado dentro de la página
 * duplicaba información y añadía ruido visual.
 *
 * Se conserva únicamente `trailing` para estados contextuales que sí
 * aportan información, por ejemplo el nivel de permisos en Administración.
 */
export default function ModuleIntro({ trailing }: Props) {
  if (!trailing) return null;

  return (
    <div className="flex justify-end px-1">
      <div className="shrink-0">{trailing}</div>
    </div>
  );
}
