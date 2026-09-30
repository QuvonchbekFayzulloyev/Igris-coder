import React, { useCallback, useState } from 'react';

interface GraphExporterProps {
  svgRef: React.RefObject<SVGSVGElement | null>;
}

export function GraphExporter({ svgRef }: GraphExporterProps) {
  const [exporting, setExporting] = useState(false);

  const exportSVG = useCallback(() => {
    if (!svgRef.current) return;
    setExporting(true);

    try {
      const svgEl = svgRef.current;
      const clone = svgEl.cloneNode(true) as SVGSVGElement;

      // Add white background for export
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('width', '100%');
      bg.setAttribute('height', '100%');
      bg.setAttribute('fill', '#09090b');
      clone.insertBefore(bg, clone.firstChild);

      // Add XML declaration and namespace
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      const svgData = new XMLSerializer().serializeToString(clone);
      const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `igris-brain-${new Date().toISOString().slice(0, 10)}.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }, [svgRef]);

  const exportPNG = useCallback(async () => {
    if (!svgRef.current) return;
    setExporting(true);

    try {
      const svgEl = svgRef.current;
      const clone = svgEl.cloneNode(true) as SVGSVGElement;

      // Add background
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('width', clone.getAttribute('width') || '620');
      bg.setAttribute('height', clone.getAttribute('height') || '380');
      bg.setAttribute('fill', '#09090b');
      clone.insertBefore(bg, clone.firstChild);

      const svgData = new XMLSerializer().serializeToString(clone);
      const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = 1240; // 2x for retina
        canvas.height = 760;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.scale(2, 2);
          ctx.drawImage(img, 0, 0);
          canvas.toBlob((blob) => {
            if (blob) {
              const pngUrl = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = pngUrl;
              a.download = `igris-brain-${new Date().toISOString().slice(0, 10)}.png`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(pngUrl);
            }
          }, 'image/png');
        }
        URL.revokeObjectURL(url);
      };
      img.src = url;
    } finally {
      setExporting(false);
    }
  }, [svgRef]);

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={exportSVG}
        disabled={exporting}
        className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-200 hover:border-zinc-500 transition-colors disabled:opacity-50"
        title="Export as SVG"
      >
        SVG
      </button>
      <button
        onClick={exportPNG}
        disabled={exporting}
        className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-200 hover:border-zinc-500 transition-colors disabled:opacity-50"
        title="Export as PNG"
      >
        PNG
      </button>
    </div>
  );
}
