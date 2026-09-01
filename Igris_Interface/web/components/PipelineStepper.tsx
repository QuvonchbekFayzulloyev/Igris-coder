import React from 'react';
import { STAGES } from '../../shared/constants';

interface PipelineStepperProps {
  current: number;
  /** REAL agent bosqichi — backend run/chat status'dan jonli keladi ("read_file → src/main.py"). */
  detail?: string;
  /** Agent hozir ishlayaptimi (task run yoki chat poll davom etmoqdami) — aktiv chiziq. */
  running?: boolean;
}

/**
 * REAL pipeline stepperi — Plan → Read → Edit → Test → Review.
 *
 * Har bir nuqta backend'ning jonli bosqichiga bog'langan (bezak emas):
 * - bajarilgan bosqichlar ✓ bilan belgilanadi
 * - faol bosqich amber rangda puls qiladi, hozirgi tool/detal yonida ko'rinadi
 * - chat ham (⚡ task'lar kabi) shu yerda jonli progress ko'rsatadi.
 */
export function PipelineStepper({ current, detail, running = false }: PipelineStepperProps) {
  const active = Math.max(0, Math.min(current, STAGES.length - 1));

  return (
    <div className="shrink-0 border-b border-zinc-800 bg-zinc-900 bg-opacity-40">
      <div className="flex items-center gap-1 px-4 py-2">
        {STAGES.map((stage, i) => {
          const state = i < active ? 'done' : i === active ? 'active' : 'pending';
          return (
            <React.Fragment key={stage}>
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    state === 'done'
                      ? 'bg-teal-400'
                      : state === 'active'
                        ? 'bg-amber-400 animate-pulse'
                        : 'bg-zinc-700'
                  }`}
                />
                <span
                  className={`text-xs font-ui ${
                    state === 'active'
                      ? 'text-amber-300 font-medium'
                      : state === 'done'
                        ? 'text-zinc-400'
                        : 'text-zinc-600'
                  }`}
                >
                  {state === 'done' ? '✓ ' : ''}
                  {stage}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div
                  className={`w-5 h-px mx-1 ${
                    i < active ? 'bg-teal-500/50' : 'bg-zinc-800'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}

        {/* Hozirgi real bosqich + bajarilayotgan tool — jonli */}
        {running && (
          <span className="ml-2 text-[10px] font-mono text-zinc-500 truncate max-w-[45%]">
            <span className="text-amber-500/80">▸</span>{' '}
            <span className="text-amber-300/90">{STAGES[active]}</span>
            {detail ? ` · ${detail}` : ' …'}
          </span>
        )}
      </div>

      {/* Jonli detal chizig'i — 0-bosqichda ham (plan) ko'rinadi, soxta emas */}
      {running && (
        <div className="px-4 pb-1.5 -mt-0.5 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
          <span className="text-[10px] font-mono text-zinc-500 truncate">
            {detail || 'ishlamoqda…'}
          </span>
        </div>
      )}
    </div>
  );
}
