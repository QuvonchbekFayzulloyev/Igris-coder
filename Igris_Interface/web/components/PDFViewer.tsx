import React, { useState, useEffect, useRef, useCallback } from 'react';

// @ts-ignore - pdfjs-dist types
import * as pdfjsLib from 'pdfjs-dist';

// Set worker source
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

interface PDFViewerProps {
  filePath: string;
  onError?: (error: string) => void;
}

export function PDFViewer({ filePath, onError }: PDFViewerProps) {
  const [pdf, setPdf] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load PDF
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const loadPdf = async () => {
      try {
        // Fetch the file and convert to ArrayBuffer
        const response = await fetch(`file://${filePath}`);
        if (!response.ok) throw new Error('Failed to fetch PDF');
        const arrayBuffer = await response.arrayBuffer();
        
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const pdfDoc = await loadingTask.promise;
        
        if (!cancelled) {
          setPdf(pdfDoc);
          setTotalPages(pdfDoc.numPages);
          setCurrentPage(1);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to load PDF';
          setError(errorMsg);
          onError?.(errorMsg);
          setLoading(false);
        }
      }
    };

    loadPdf();
    return () => { cancelled = true; };
  }, [filePath, onError]);

  // Render current page
  useEffect(() => {
    if (!pdf || !canvasRef.current || rendering) return;

    let cancelled = false;
    setRendering(true);

    const renderPage = async () => {
      try {
        const page = await pdf.getPage(currentPage);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        
        if (!canvas || cancelled) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({
          canvasContext: ctx,
          viewport: viewport
        }).promise;

        if (!cancelled) {
          setRendering(false);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Render error:', err);
          setRendering(false);
        }
      }
    };

    renderPage();
    return () => { cancelled = true; };
  }, [pdf, currentPage, scale]);

  // Navigation
  const goToPage = useCallback((page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  }, [totalPages]);

  const prevPage = useCallback(() => goToPage(currentPage - 1), [currentPage, goToPage]);
  const nextPage = useCallback(() => goToPage(currentPage + 1), [currentPage, goToPage]);

  // Zoom
  const zoomIn = useCallback(() => setScale(s => Math.min(3, s + 0.25)), []);
  const zoomOut = useCallback(() => setScale(s => Math.max(0.5, s - 0.25)), []);
  const resetZoom = useCallback(() => setScale(1.5), []);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault();
        prevPage();
      } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
        e.preventDefault();
        nextPage();
      } else if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        zoomIn();
      } else if (e.key === '-') {
        e.preventDefault();
        zoomOut();
      } else if (e.key === '0') {
        e.preventDefault();
        resetZoom();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [prevPage, nextPage, zoomIn, zoomOut, resetZoom]);

  if (loading) {
    return (
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center">
        <div className="text-zinc-400 font-mono text-sm">PDF yuklanmoqda...</div>
        <div className="mt-2 w-32 h-1 bg-zinc-800 rounded overflow-hidden">
          <div className="h-full bg-amber-500 animate-pulse" style={{ width: '60%' }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center">
        <div className="text-red-400 font-mono text-sm">Xatolik: {error}</div>
        <a
          href={`file://${filePath}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 text-blue-400 hover:text-blue-300 text-xs font-mono"
        >
          Brauzerda ochish →
        </a>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Controls */}
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800 shrink-0">
        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={prevPage}
            disabled={currentPage <= 1}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            ←
          </button>
          <span className="text-xs font-mono text-zinc-400">
            <input
              type="number"
              value={currentPage}
              onChange={(e) => goToPage(parseInt(e.target.value) || 1)}
              min={1}
              max={totalPages}
              className="w-12 bg-zinc-800 border border-zinc-700 rounded px-1 py-0.5 text-center text-xs font-mono text-white"
            />
            <span className="mx-1">/</span>
            <span>{totalPages}</span>
          </span>
          <button
            onClick={nextPage}
            disabled={currentPage >= totalPages}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            →
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            −
          </button>
          <button
            onClick={resetZoom}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 rounded min-w-[50px]"
          >
            {Math.round(scale * 100)}%
          </button>
          <button
            onClick={zoomIn}
            disabled={scale >= 3}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            +
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <a
            href={`file://${filePath}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] font-mono text-blue-400 hover:text-blue-300"
          >
            yangi oynada →
          </a>
        </div>
      </div>

      {/* PDF Canvas */}
      <div 
        ref={containerRef}
        className="flex-1 min-h-0 overflow-auto bg-zinc-950 flex items-start justify-center p-4"
      >
        <canvas
          ref={canvasRef}
          className="shadow-2xl"
          style={{ maxWidth: '100%' }}
        />
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-1 bg-zinc-900 border-t border-zinc-800 text-[10px] font-mono text-zinc-500 shrink-0">
        <span>PDF.js v{pdfjsLib.version}</span>
        <span>
          {rendering && <span className="text-amber-400 animate-pulse">● </span>}
          Sahifa {currentPage} / {totalPages} · {Math.round(scale * 100)}%
        </span>
      </div>
    </div>
  );
}
