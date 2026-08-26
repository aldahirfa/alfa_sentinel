import type { HoneyfileListItem } from "../types/honeyfiles";
import { fileTypeIcon, honeyfileStatusPillStyle, HONEYFILE_STATUS_LABEL } from "../lib/honeyfileStatus";
import { rowSelectionStyle } from "../lib/rowSelection";

interface Props {
  honeyfiles: HoneyfileListItem[];
  loading: boolean;
  hasFilters: boolean;
  onSelect: (id: number) => void;
  selectedId: number | null;
  flashId: number | null;
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

export default function HoneyfilesTable({ honeyfiles, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
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
        {!loading && <div className="ml-auto text-[9.5px] px-2.5 py-1.5 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{honeyfiles.length} visibles</div>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px] min-w-[980px]">
          <thead style={{ background: "color-mix(in srgb, var(--surf2) 88%, transparent)" }}>
            <tr className="text-left text-[8.5px] tracking-[.14em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
              <th className="px-4 py-3 font-semibold">Honeyfile</th>
              <th className="px-3 py-3 font-semibold">Endpoint</th>
              <th className="px-3 py-3 font-semibold">Tipo</th>
              <th className="px-3 py-3 font-semibold">Estado</th>
              <th className="px-3 py-3 font-semibold">Último chequeo</th>
              <th className="px-4 py-3 font-semibold text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 7 }).map((_, i) => <SkeletonRow key={i} />)
            ) : honeyfiles.length === 0 ? (
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
              honeyfiles.map((hf) => {
                const triggered = hf.status === "TRIGGERED";
                const accent = triggered ? "var(--crit)" : "var(--brand)";
                const isSelected = hf.id === selectedId;
                const selStyle = rowSelectionStyle(isSelected, hf.id === flashId);

                return (
                  <tr
                    key={hf.id}
                    className="border-t cursor-pointer transition-premium"
                    style={{ borderColor: "var(--line-soft)", ...selStyle, boxShadow: `inset 3px 0 0 ${accent}` }}
                    onClick={() => onSelect(hf.id)}
                    onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = triggered ? "var(--crit-fill)" : "var(--surf2)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = (selStyle.background as string) || "transparent"; }}
                  >
                    <td className="px-4 py-3.5 min-w-[300px]">
                      <div className="flex items-start gap-3">
                        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: triggered ? "var(--crit-soft)" : "var(--brand-soft)", color: accent }}>
                          <i className={fileTypeIcon(hf.file_type)} style={{ fontSize: "16px" }} />
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold truncate" style={{ color: triggered ? "var(--crit)" : "var(--tx)" }}>{hf.file_name}</div>
                          <div className="mono-data text-[9px] mt-1 truncate max-w-[300px]" style={{ color: "var(--tx-mute)" }}>{hf.file_path}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="font-medium" style={{ color: "var(--tx-dim)" }}>{hf.hostname}</div>
                      <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>{hf.operating_system} {hf.os_version}</div>
                    </td>
                    <td className="px-3 py-3.5"><span className="text-[9px] font-semibold px-2 py-1 rounded-lg" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)", color: "var(--tx-dim)" }}>{hf.file_type}</span></td>
                    <td className="px-3 py-3.5">
                      <span className="text-[9px] font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5" style={honeyfileStatusPillStyle(hf.status)}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: triggered ? "var(--crit)" : hf.status === "ACTIVE" ? "var(--ok)" : "var(--off)" }} />
                        {HONEYFILE_STATUS_LABEL[hf.status]}
                        {hf.activations_count > 0 && ` · ${hf.activations_count}`}
                      </span>
                    </td>
                    <td className="px-3 py-3.5 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>{hf.last_checked_at ?? "—"}</td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelect(hf.id); }}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover whitespace-nowrap"
                        style={{ background: "var(--brand-fill)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}
                      >
                        <i className="ph ph-eye" style={{ fontSize: "13px" }} />
                        <span className="text-[10px] font-semibold">Ver detalles</span>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
