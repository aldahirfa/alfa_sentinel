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
        <td key={i} className="py-3 pr-3">
          <div
            className="h-3.5 rounded animate-pulse"
            style={{ background: "var(--surf3)", width: i === 0 ? "70%" : "50%" }}
          />
        </td>
      ))}
    </tr>
  );
}

export default function HoneyfilesTable({ honeyfiles, loading, hasFilters, onSelect, selectedId, flashId }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="text-left text-[10.5px] tracking-wider uppercase" style={{ color: "var(--tx-mute)" }}>
            <th className="pb-2 pr-3 font-semibold">Honeyfile / Ruta</th>
            <th className="pb-2 pr-3 font-semibold">Endpoint / SO</th>
            <th className="pb-2 pr-3 font-semibold">Tipo</th>
            <th className="pb-2 pr-3 font-semibold">Estado</th>
            <th className="pb-2 pr-3 font-semibold">Últ. chequeo</th>
            <th className="pb-2 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
          ) : honeyfiles.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center py-10" style={{ color: "var(--tx-mute)" }}>
                <i className="ph ph-file-lock text-xl block mb-2" />
                {hasFilters
                  ? "Ningún honeyfile coincide con la búsqueda o los filtros aplicados."
                  : "Todavía no hay honeyfiles desplegados. Usá \"Desplegar honeyfile\" para crear el primero."}
              </td>
            </tr>
          ) : (
            honeyfiles.map((hf) => {
              const accent = hf.status === "TRIGGERED" ? "var(--crit)" : null;
              const isSelected = hf.id === selectedId;
              const isFlashing = hf.id === flashId;
              const selStyle = rowSelectionStyle(isSelected, isFlashing);
              return (
                <tr
                  key={hf.id}
                  className="border-t"
                  style={{ borderColor: "var(--line-soft)", ...selStyle }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surf2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = selStyle.background as string)}
                >
                  <td className="py-2.5 pr-3" style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}>
                    <div className="flex items-start gap-2 pl-2">
                      <i className={fileTypeIcon(hf.file_type)} style={{ fontSize: "16px", color: "var(--tx-mute)", marginTop: "1px" }} />
                      <div className="min-w-0">
                        <div className="font-semibold" style={{ color: "var(--tx)" }}>{hf.file_name}</div>
                        <div className="text-[10.5px] mt-0.5 truncate max-w-[220px]" style={{ color: "var(--tx-mute)" }}>{hf.file_path}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 pr-3">
                    <div style={{ color: "var(--tx-dim)" }}>{hf.hostname}</div>
                    <div className="text-[10.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{hf.operating_system} {hf.os_version}</div>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className="text-[10.5px] font-medium px-1.5 py-0.5 rounded" style={{ border: "1px solid var(--line)", color: "var(--tx-dim)" }}>
                      {hf.file_type}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="text-[10.5px] font-medium px-2 py-0.5 rounded inline-flex items-center gap-1.5 w-fit"
                      style={honeyfileStatusPillStyle(hf.status)}
                    >
                      {HONEYFILE_STATUS_LABEL[hf.status]}
                      {hf.activations_count > 0 && ` · ${hf.activations_count}`}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3" style={{ color: "var(--tx-mute)" }}>
                    {hf.last_checked_at ?? "—"}
                  </td>
                  <td className="py-2.5">
                    <button
                      onClick={() => onSelect(hf.id)}
                      className="flex items-center gap-1 text-[11.5px] font-medium border-0 bg-transparent cursor-pointer whitespace-nowrap"
                      style={{ color: "var(--brand)" }}
                    >
                      Detalles
                      <i className="ph ph-arrow-right text-[12px]" />
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </section>
  );
}
