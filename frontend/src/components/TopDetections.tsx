import type { TopDetection } from "../types/dashboard";

interface Props {
  data: TopDetection[];
}

export default function TopDetections({ data }: Props) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const total = data.reduce((sum, item) => sum + item.count, 0);

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-chart-bar" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>
            Tendencia de detección
          </div>
          <h2 className="text-[14.5px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Principales tipos de detección
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Reglas con mayor actividad durante las últimas 24 horas
          </div>
        </div>
        <div className="ml-auto text-right">
          <div className="text-[21px] font-bold leading-none tabular-nums" style={{ color: "var(--tx)" }}>{total}</div>
          <div className="text-[9px] mt-1" style={{ color: "var(--tx-mute)" }}>detecciones</div>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="flex-1 min-h-[190px] flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
            <i className="ph ph-shield-check" style={{ fontSize: "19px" }} />
          </div>
          <div className="text-[10.5px] mt-3" style={{ color: "var(--tx-mute)" }}>Todavía no hay detecciones registradas.</div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 mt-4">
          {data.map((d, index) => {
            const width = Math.max(3, (d.count / max) * 100);
            return (
              <div
                key={d.rule_name}
                className="rounded-xl px-3 py-3"
                style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-7 h-7 rounded-lg grid place-items-center shrink-0 text-[9px] font-bold mono-data"
                    style={{ background: index === 0 ? "var(--brand)" : "var(--brand-soft)", color: index === 0 ? "#fff" : "var(--brand)" }}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold truncate" style={{ color: "var(--tx)" }}>{d.rule_label}</span>
                      <span className="ml-auto text-[11px] font-bold tabular-nums" style={{ color: "var(--tx)" }}>{d.count}</span>
                    </div>
                    <div className="h-[5px] rounded-full overflow-hidden mt-2" style={{ background: "var(--surf3)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${width}%`,
                          background: index === 0 ? "linear-gradient(90deg, var(--brand-strong), var(--info))" : "var(--brand)",
                          opacity: index === 0 ? 1 : Math.max(.42, 1 - index * .12),
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
