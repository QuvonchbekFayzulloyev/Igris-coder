/* ---------------------------------------------------------------------
   CLI-specific color mappings using Ink colors
   These are rendering-specific and should NOT be in shared/
--------------------------------------------------------------------- */

export const KIND_COLOR_INK = {
  fact: { dot: 'yellow', text: 'yellow', fill: '#fbbf24' },
  session: { dot: 'green', text: 'green', fill: '#2dd4bf' },
  pattern: { dot: 'magenta', text: 'magenta', fill: '#a78bfa' },
  architecture: { dot: 'blue', text: 'blue', fill: '#38bdf8' },
} as const;

export type NodeKind = keyof typeof KIND_COLOR_INK;
