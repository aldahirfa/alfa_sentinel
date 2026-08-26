import type { ReactNode } from "react";
import { ModuleMark, type Page } from "./ModuleMark";

interface Props {
  page: Page;
  eyebrow: string;
  title: string;
  description: string;
  trailing?: ReactNode;
}

export default function ModuleIntro({ page, eyebrow, title, description, trailing }: Props) {
  return (
    <section className="module-intro px-1 py-1 flex items-start justify-between gap-4 flex-wrap">
      <div className="flex items-start gap-3.5 min-w-0">
        <div
          className="w-10 h-10 rounded-xl border grid place-items-center shrink-0 mt-0.5"
          style={{
            background: "linear-gradient(145deg, var(--brand-soft), var(--brand-fill))",
            borderColor: "color-mix(in srgb, var(--brand) 18%, var(--line-soft))",
            color: "var(--brand)",
          }}
        >
          <ModuleMark page={page} size={18} />
        </div>
        <div className="min-w-0">
          <div className="text-[9px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>
            {eyebrow}
          </div>
          <h2 className="m-0 mt-1 text-[15px] font-semibold tracking-[-.015em]" style={{ color: "var(--tx)" }}>
            {title}
          </h2>
          <p className="m-0 mt-1.5 max-w-[760px] text-[10.5px] leading-relaxed" style={{ color: "var(--tx-mute)" }}>
            {description}
          </p>
        </div>
      </div>
      {trailing && <div className="shrink-0 self-center">{trailing}</div>}
    </section>
  );
}
