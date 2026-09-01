/* ---------------------------------------------------------------------
   Web-specific color mappings using Tailwind CSS classes
   These are rendering-specific and should NOT be in shared/
--------------------------------------------------------------------- */

export const KIND_COLOR_TAILWIND = {
  fact: { dot: 'bg-amber-400', text: 'text-amber-300', fill: '#fbbf24' },
  session: { dot: 'bg-teal-400', text: 'text-teal-300', fill: '#2dd4bf' },
  pattern: { dot: 'bg-violet-400', text: 'text-violet-300', fill: '#a78bfa' },
  architecture: { dot: 'bg-sky-400', text: 'text-sky-300', fill: '#38bdf8' },
} as const;

export type NodeKind = keyof typeof KIND_COLOR_TAILWIND;
