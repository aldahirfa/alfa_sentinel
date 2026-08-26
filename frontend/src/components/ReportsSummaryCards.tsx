interface Props {
  totalReports: number;
  lastGeneratedAt: string | null;
  lastGeneratedBy: string | null;
}

export default function ReportsSummaryCards({ totalReports, lastGeneratedAt, lastGeneratedBy }: Props) {
  return (
    <section className="soc-panel-strong rounded-[22px] overflow-hidden relative">
      <div
        className="absolute -top-24 -right-20 w-[300px] h-[300px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, var(--brand-glow), transparent 68%)", opacity: .55 }}
      />
      <div className="relative z-[1] p-5 grid grid-cols-1 lg:grid-cols-[1.25fr_.75fr] gap-4 items-stretch">
        <div className="flex items-center gap-4 min-w-0">
          <div className="w-14 h-14 rounded-[18px] grid place-items-center shrink-0 border" style={{ background: "var(--brand-soft)", color: "var(--brand)", borderColor: "var(--brand-soft)" }}>
            <i className="ph ph-files" style={{ fontSize: "26px" }} />
          </div>
          <div className="min-w-0">
            <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Repositorio documental</div>
            <div className="flex items-end gap-3 mt-1.5">
              <div className="text-[34px] font-bold tracking-[-.045em] leading-none tabular-nums" style={{ color: "var(--tx)" }}>{totalReports}</div>
              <div className="text-[11px] pb-1" style={{ color: "var(--tx-mute)" }}>informes generados</div>
            </div>
            <div className="text-[10.5px] mt-2 max-w-[620px] leading-relaxed" style={{ color: "var(--tx-dim)" }}>
              Informes consolidados de seguridad, actividad de endpoints e incidentes disponibles para consulta y respaldo institucional.
            </div>
          </div>
        </div>

        <div className="rounded-2xl border p-4 flex items-center gap-3" style={{ background: "color-mix(in srgb, var(--surf2) 84%, transparent)", borderColor: "var(--line-soft)" }}>
          <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
            <i className="ph ph-clock-counter-clockwise" style={{ fontSize: "18px" }} />
          </div>
          <div className="min-w-0">
            <div className="text-[9px] font-bold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>Último informe</div>
            <div className="text-[12px] font-semibold mt-1 truncate" style={{ color: "var(--tx)" }}>{lastGeneratedAt ?? "Sin informes generados"}</div>
            <div className="text-[9.5px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>{lastGeneratedBy ? `Generado por ${lastGeneratedBy}` : "Aún no existe un responsable registrado"}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
