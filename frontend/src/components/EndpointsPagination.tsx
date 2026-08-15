interface Props {
  page: number;
  pageSize: number;
  totalPages: number;
  filteredTotal: number;
  onPageChange: (page: number) => void;
}

export default function EndpointsPagination({ page, pageSize, totalPages, filteredTotal, onPageChange }: Props) {
  if (filteredTotal === 0) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, filteredTotal);

  return (
    <div className="flex items-center justify-between px-1">
      <span className="text-[11.5px]" style={{ color: "var(--tx-mute)" }}>
        Mostrando {start}–{end} de {filteredTotal} endpoints
      </span>
      <div className="flex items-center gap-1.5">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="w-[30px] h-[30px] rounded-lg border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
        >
          <i className="ph ph-caret-left text-xs" />
        </button>
        <span className="text-[11.5px] px-2" style={{ color: "var(--tx-dim)" }}>
          Página {page} de {totalPages}
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="w-[30px] h-[30px] rounded-lg border grid place-items-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
        >
          <i className="ph ph-caret-right text-xs" />
        </button>
      </div>
    </div>
  );
}
