/* ---------------------------------------------------------------------
   Color constants - Platform-agnostic color values
   Tailwind classes are in web/components/, Ink colors in cli/
--------------------------------------------------------------------- */

export const COLORS = {
  amber: { hex: '#fbbf24', ink: 'yellow' },
  teal: { hex: '#2dd4bf', ink: 'green' },
  violet: { hex: '#a78bfa', ink: 'magenta' },
  sky: { hex: '#38bdf8', ink: 'blue' },
  rose: { hex: '#fb7185', ink: 'red' },
  zinc: {
    50: '#fafafa',
    100: '#f4f4f5',
    200: '#e4e4e7',
    300: '#d4d4d8',
    400: '#a1a1aa',
    500: '#71717a',
    600: '#52525b',
    700: '#3f3f46',
    800: '#27272a',
    900: '#18181b',
    950: '#09090b',
  },
} as const;

export const KIND_COLORS = {
  fact: { hex: COLORS.amber.hex, ink: COLORS.amber.ink },
  session: { hex: COLORS.teal.hex, ink: COLORS.teal.ink },
  pattern: { hex: COLORS.violet.hex, ink: COLORS.violet.ink },
  architecture: { hex: COLORS.sky.hex, ink: COLORS.sky.ink },
} as const;
