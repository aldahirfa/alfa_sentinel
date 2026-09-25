import { Fragment, useState } from "react";
import DateCell from "./DateCell";
import type { HoneyfileAssignmentStatus, HoneyfileListItem, HoneyfileTemplate } from "../types/honeyfiles";
import {
  fileTypeIcon, honeyfileStatusPillStyle, HONEYFILE_STATUS_LABEL,
  HONEYFILE_LOCATION_LABEL, HONEYFILE_PLATFORM_LABEL,
} from "../lib/honeyfileStatus";
import { CONN_STATUS_LABEL, CONN_STATUS_VAR } from "../lib/endpointStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  honeyfiles: HoneyfileListItem[];
  templates: HoneyfileTemplate[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
  selectedId: number | null;
  flashId: number | null;
}

// Un endpoint asignado a un señuelo que todavía no tiene el archivo
// registrado en 'honeyfiles': pendiente, fallido, o el agente lo dio
// por creado pero el servidor no tiene la fila (inconsistencia real).
interface MissingDeployment {
  agent_id: number;
  hostname: string;
  operating_system: string;
  status: HoneyfileAssignmentStatus;
}

// Una fila de la tabla = un señuelo. Las instancias (un archivo en un
// endpoint) se ven al desplegarlo, así el mismo archivo no se repite.
interface HoneyfileGroup {
  key: string;
  template: HoneyfileTemplate | null;
  fileName: string;
  fileType: string;
  instances: HoneyfileListItem[];
  missing: MissingDeployment[];
}

const MISSING_LABEL: Record<HoneyfileAssignmentStatus, string> = {
  PENDING: "Pendiente de crear",
  FAILED: "Falló la creación",
  CREATED: "Sin registro en el servidor",
};

const MISSING_VAR: Record<HoneyfileAssignmentStatus, string> = {
  PENDING: "var(--warn)",
  FAILED: "var(--crit)",
  CREATED: "var(--warn)",
};

function buildGroups(honeyfiles: HoneyfileListItem[], templates: HoneyfileTemplate[], hasFilters: boolean): HoneyfileGroup[] {
  const known = new Set(templates.map((t) => t.id));
  const groups: HoneyfileGroup[] = [];

  for (const t of templates) {
    const instances = honeyfiles.filter((hf) => hf.template_id === t.id);
    const withFile = new Set(instances.map((hf) => hf.agent_id));
    // Con filtros activos se muestran solo los despliegues que coinciden;
    // lo pendiente/fallido no tiene endpoint real contra el cual filtrar.
    const missing = hasFilters ? [] : t.assignments.filter((a) => !withFile.has(a.agent_id));
    if (instances.length === 0 && (hasFilters || !t.is_active)) continue;
    groups.push({ key: `t:${t.id}`, template: t, fileName: t.file_name, fileType: t.file_type, instances, missing });
  }

  // Honeyfiles sin plantilla (anteriores a las plantillas): se agrupan por nombre.
  const legacy = new Map<string, HoneyfileListItem[]>();
  for (const hf of honeyfiles) {
    if (hf.template_id !== null && known.has(hf.template_id)) continue;
    legacy.set(hf.file_name, [...(legacy.get(hf.file_name) ?? []), hf]);
  }
  for (const [name, instances] of legacy) {
    groups.push({ key: `f:${name}`, template: null, fileName: name, fileType: instances[0].file_type, instances, missing: [] });
  }
  return groups;
}

// "dd/mm/aaaa HH:MM:SS" (formato del servidor) -> número comparable.
function dateKey(value: string | null): number {
  const m = value?.match(/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})$/);
  return m ? Number(`${m[3]}${m[2]}${m[1]}${m[4]}${m[5]}${m[6]}`) : 0;
}

function latestCheck(instances: HoneyfileListItem[]): string | null {
  let best: string | null = null;
  for (const hf of instances) if (dateKey(hf.last_checked_at) > dateKey(best)) best = hf.last_checked_at;
  return best;
}

function SkeletonRow() {
  return (
    <tr className="border-t" style={{ borderColor: "var(--line-soft)" }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="px-3 py-3.5">
          <div className="h-3 rounded animate-pulse" style={{ background: "var(--surf3)", width: i === 0 ? "76%" : "56%" }} />
        </td>
      ))}
    </tr>
  );
}

function GroupStatus({ group }: { group: HoneyfileGroup }) {
  const triggered = group.instances.filter((hf) => hf.status === "TRIGGERED");
  if (triggered.length > 0) {
    const activations = triggered.reduce((n, hf) => n + hf.activations_count, 0);
    return (
      <span
        className="text-[9px] font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5 whitespace-nowrap"
        style={honeyfileStatusPillStyle("TRIGGERED")}
        title={`${activations} activación${activations === 1 ? "" : "es"} registrada${activations === 1 ? "" : "s"}`}
      >
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#fff" }} />
        Activado en {triggered.length} endpoint{triggered.length === 1 ? "" : "s"}
      </span>
    );
  }
  if (group.instances.length === 0) {
    return <span className="text-[9.5px]" style={{ color: "var(--tx-mute)" }}>Sin desplegar</span>;
  }
  const status = group.instances.every((hf) => hf.status === "INACTIVE") ? "INACTIVE" : "ACTIVE";
  return (
    <span className="text-[9px] font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5" style={honeyfileStatusPillStyle(status)}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: status === "ACTIVE" ? "var(--ok)" : "var(--off)" }} />
      {HONEYFILE_STATUS_LABEL[status]}
    </span>
  );
}

function Coverage({ group }: { group: HoneyfileGroup }) {
  const n = group.instances.length;
  const counts = group.missing.reduce<Record<string, number>>((acc, m) => ({ ...acc, [m.status]: (acc[m.status] ?? 0) + 1 }), {});
  return (
    <div>
      <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>{n} endpoint{n === 1 ? "" : "s"}</div>
      {group.missing.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-1">
          {(["PENDING", "FAILED", "CREATED"] as const).filter((s) => counts[s]).map((s) => (
            <span key={s} className="text-[8.5px] font-semibold" style={{ color: MISSING_VAR[s] }}>
              {counts[s]} {s === "PENDING" ? "pendiente" : s === "FAILED" ? "fallido" : "sin registro"}{counts[s] === 1 ? "" : "s"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function DeploymentsPanel({ group, onSelect, selectedId, flashId }: { group: HoneyfileGroup; onSelect: (id: number) => void; selectedId: number | null; flashId: number | null }) {
  return (
    <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--line-soft)", background: "var(--surf2)" }}>
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="text-left text-[8px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
            <th className="px-4 py-2.5 font-semibold">Endpoint</th>
            <th className="px-3 py-2.5 font-semibold">Ruta en el equipo</th>
            <th className="px-3 py-2.5 font-semibold">Estado</th>
            <th className="px-3 py-2.5 font-semibold">Conexión</th>
            <th className="px-3 py-2.5 font-semibold">Último chequeo</th>
            <th className="px-4 py-2.5 font-semibold text-right">Acción</th>
          </tr>
        </thead>
        <tbody>
          {group.instances.map((hf) => {
            const isSelected = hf.id === selectedId;
            const selStyle = rowSelectionStyle(isSelected, hf.id === flashId);
            const conn = hf.is_agent_live ? "ONLINE" : "OFFLINE";
            return (
              <tr
                key={hf.id}
                className="border-t cursor-pointer transition-premium"
                style={{ borderColor: "var(--line-soft)", ...selStyle }}
                onClick={() => onSelect(hf.id)}
                onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "var(--surf3)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = (selStyle.background as string) || "transparent"; }}
              >
                <td className="px-4 py-2.5">
                  <div className="font-medium" style={{ color: "var(--tx-dim)" }}>{hf.hostname}</div>
                  <div className="text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{hf.operating_system} {hf.os_version}</div>
                </td>
                <td className="px-3 py-2.5 mono-data text-[9px] max-w-[340px] truncate" style={{ color: "var(--tx-mute)" }} title={hf.file_path}>{hf.file_path}</td>
                <td className="px-3 py-2.5">
                  <span className="text-[9px] font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5 whitespace-nowrap" style={honeyfileStatusPillStyle(hf.status)}>
                    {HONEYFILE_STATUS_LABEL[hf.status]}
                    {hf.activations_count > 0 && ` · ${hf.activations_count}`}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className="inline-flex items-center gap-1.5 text-[10px] whitespace-nowrap" style={{ color: "var(--tx-dim)" }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: CONN_STATUS_VAR[conn] }} />
                    {CONN_STATUS_LABEL[conn]}
                  </span>
                </td>
                <DateCell value={hf.last_checked_at} className="px-3 py-2.5" />
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); onSelect(hf.id); }}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border cursor-pointer transition-premium btn-hover whitespace-nowrap"
                    style={{ background: "var(--brand-fill)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}
                  >
                    <i className="ph ph-eye" style={{ fontSize: "12px" }} />
                    <span className="text-[9.5px] font-semibold">Ver detalle</span>
                  </button>
                </td>
              </tr>
            );
          })}
          {group.missing.map((m) => (
            <tr key={`m:${m.agent_id}`} className="border-t" style={{ borderColor: "var(--line-soft)" }}>
              <td className="px-4 py-2.5">
                <div className="font-medium" style={{ color: "var(--tx-dim)" }}>{m.hostname}</div>
                <div className="text-[9px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{m.operating_system}</div>
              </td>
              <td className="px-3 py-2.5 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>—</td>
              <td className="px-3 py-2.5" colSpan={4}>
                <span className="inline-flex items-center gap-1.5 text-[9.5px] font-semibold" style={{ color: MISSING_VAR[m.status] }}>
                  <i className={m.status === "FAILED" ? "ph ph-x-circle" : "ph ph-clock"} style={{ fontSize: "12px" }} />
                  {MISSING_LABEL[m.status]}
                </span>
              </td>
            </tr>
          ))}
          {group.instances.length === 0 && group.missing.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-4 text-center text-[10px]" style={{ color: "var(--tx-mute)" }}>Este señuelo todavía no está asignado a ningún endpoint.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function HoneyfilesTable({ honeyfiles, templates, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  // Con filtros activos los señuelos arrancan desplegados (se busca un
  // endpoint o una ruta concreta); sin filtros, plegados. 'toggled'
  // guarda los que el analista cambió respecto de ese valor inicial.
  const [toggled, setToggled] = useState<Set<string>>(new Set());
  const groups = buildGroups(honeyfiles, templates, hasFilters);

  function toggle(key: string) {
    setToggled((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-file-lock" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Inventario de señuelos</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Honeyfiles desplegados</div>
        </div>
        {!loading && (
          <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>
            {groups.length} señuelo{groups.length === 1 ? "" : "s"} · {honeyfiles.length} despliegue{honeyfiles.length === 1 ? "" : "s"}
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[980px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Honeyfile</th>
              <th className="px-3 py-3 font-semibold">Cobertura</th>
              <th className="px-3 py-3 font-semibold">Tipo</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Último chequeo</th>
              <th className="px-4 py-3 font-semibold text-right">Endpoints</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            ) : groups.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-14" style={{ color: "var(--tx-mute)" }}>
                  <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: hasFilters ? "var(--brand-soft)" : "var(--surf3)", color: hasFilters ? "var(--brand)" : "var(--tx-mute)" }}>
                    <i className={hasFilters ? "ph ph-magnifying-glass" : "ph ph-file-lock"} style={{ fontSize: "22px" }} />
                  </div>
                  <div className="font-semibold" style={{ color: "var(--tx-dim)" }}>{hasFilters ? "Sin coincidencias" : "Sin honeyfiles desplegados"}</div>
                  <div className="text-[9.5px] mt-1">{hasFilters ? "Ajusta los filtros para ampliar la búsqueda." : "Usa “Desplegar honeyfile” para crear el primer señuelo."}</div>
                </td>
              </tr>
            ) : (
              groups.map((group) => {
                const expanded = hasFilters !== toggled.has(group.key);
                const triggered = group.instances.some((hf) => hf.status === "TRIGGERED");
                const accent = triggered ? "var(--crit)" : "var(--brand)";
                const t = group.template;
                const subtitle = t
                  ? `${HONEYFILE_LOCATION_LABEL[t.location] ?? t.location} · ${HONEYFILE_PLATFORM_LABEL[t.platform] ?? t.platform}${t.auto_deploy ? " · automático" : ""}`
                  : "Sin plantilla (despliegue anterior)";

                return (
                  <Fragment key={group.key}>
                    <tr
                      className="border-t cursor-pointer transition-premium"
                      style={{ borderColor: "var(--line-soft)", boxShadow: `inset 3px 0 0 ${accent}`, background: expanded ? "var(--surf2)" : "transparent" }}
                      onClick={() => toggle(group.key)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = triggered ? "var(--crit-fill)" : "var(--surf2)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = expanded ? "var(--surf2)" : "transparent"; }}
                      aria-expanded={expanded}
                    >
                      <td className="px-4 py-3.5 min-w-[300px]">
                        <div className="flex items-start gap-3">
                          <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: triggered ? "var(--crit-soft)" : "var(--brand-soft)", color: accent }}>
                            <i className={fileTypeIcon(group.fileType)} style={{ fontSize: "16px" }} />
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold truncate" style={{ color: triggered ? "var(--crit)" : "var(--tx)" }}>{group.fileName}</div>
                            <div className="text-[9px] mt-1 truncate max-w-[300px]" style={{ color: "var(--tx-mute)" }}>{subtitle}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3.5"><Coverage group={group} /></td>
                      <td className="px-3 py-3.5"><span className="text-[9px] font-semibold px-2 py-1 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx-dim)" }}>{group.fileType}</span></td>
                      <td className="px-3 py-3.5"><GroupStatus group={group} /></td>
                      <DateCell value={latestCheck(group.instances)} />
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); toggle(group.key); }}
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover whitespace-nowrap"
                          style={{ background: "var(--brand-fill)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}
                        >
                          <span className="text-[10px] font-semibold">{expanded ? "Ocultar" : "Ver endpoints"}</span>
                          <i className={expanded ? "ph ph-caret-up" : "ph ph-caret-down"} style={{ fontSize: "12px" }} />
                        </button>
                      </td>
                    </tr>
                    {expanded && (
                      <tr style={{ background: "var(--surf2)" }}>
                        <td colSpan={6} className="px-4 pb-4 pt-1" style={{ boxShadow: `inset 3px 0 0 ${accent}` }}>
                          <DeploymentsPanel group={group} onSelect={onSelect} selectedId={selectedId} flashId={flashId} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
