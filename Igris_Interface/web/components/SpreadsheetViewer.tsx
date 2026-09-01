import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as XLSX from 'xlsx';

interface SpreadsheetViewerProps {
  filePath: string;
  onError?: (error: string) => void;
}

interface SheetData {
  name: string;
  data: any[][];
  range: string;
  rows: number;
  cols: number;
}

export function SpreadsheetViewer({ filePath, onError }: SpreadsheetViewerProps) {
  const [workbook, setWorkbook] = useState<XLSX.WorkBook | null>(null);
  const [sheets, setSheets] = useState<SheetData[]>([]);
  const [activeSheetIndex, setActiveSheetIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cellSelection, setCellSelection] = useState<{ row: number; col: number } | null>(null);
  const [columnWidths, setColumnWidths] = useState<number[]>([]);

  // Load Excel file
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const loadExcel = async () => {
      try {
        const response = await fetch(`file://${filePath}`);
        if (!response.ok) throw new Error('Failed to fetch Excel file');
        
        const arrayBuffer = await response.arrayBuffer();
        const data = new Uint8Array(arrayBuffer);
        const wb = XLSX.read(data, { type: 'array', cellStyles: true, cellDates: true });
        
        if (!cancelled) {
          setWorkbook(wb);
          
          // Parse all sheets
          const parsedSheets: SheetData[] = wb.SheetNames.map((name) => {
            const sheet = wb.Sheets[name];
            const jsonData = XLSX.utils.sheet_to_json<any[]>(sheet, { header: 1, defval: '' });
            const range = XLSX.utils.decode_range(sheet['!ref'] || 'A1');
            
            return {
              name,
              data: jsonData,
              range: sheet['!ref'] || 'A1',
              rows: jsonData.length,
              cols: range.e.c + 1,
            };
          });
          
          setSheets(parsedSheets);
          setActiveSheetIndex(0);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to load Excel file';
          setError(errorMsg);
          onError?.(errorMsg);
          setLoading(false);
        }
      }
    };

    loadExcel();
    return () => { cancelled = true; };
  }, [filePath, onError]);

  // Calculate column widths based on content
  const calculateColumnWidths = useCallback((data: any[][]) => {
    const widths: number[] = [];
    const maxCols = Math.max(...data.map(row => row.length), 0);
    
    for (let col = 0; col < maxCols; col++) {
      let maxWidth = 60; // minimum width
      for (let row = 0; row < Math.min(data.length, 100); row++) {
        const cellValue = String(data[row]?.[col] ?? '');
        // Approximate width: each character ~8px, plus padding
        const cellWidth = Math.min(cellValue.length * 8 + 20, 300);
        maxWidth = Math.max(maxWidth, cellWidth);
      }
      widths.push(maxWidth);
    }
    return widths;
  }, []);

  // Update column widths when sheet changes
  useEffect(() => {
    if (sheets[activeSheetIndex]) {
      setColumnWidths(calculateColumnWidths(sheets[activeSheetIndex].data));
      setCellSelection(null);
    }
  }, [activeSheetIndex, sheets, calculateColumnWidths]);

  // Format cell value for display
  const formatCellValue = useCallback((value: any): string => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'number') {
      // Format numbers with appropriate decimal places
      if (Number.isInteger(value)) return value.toLocaleString();
      return value.toFixed(2);
    }
    if (value instanceof Date) {
      return value.toLocaleDateString();
    }
    return String(value);
  }, []);

  // Get cell type for styling
  const getCellType = useCallback((value: any): string => {
    if (value === null || value === undefined) return 'empty';
    if (typeof value === 'number') return 'number';
    if (value instanceof Date) return 'date';
    if (typeof value === 'boolean') return 'boolean';
    return 'text';
  }, []);

  // Handle cell click
  const handleCellClick = useCallback((row: number, col: number) => {
    setCellSelection({ row, col });
  }, []);

  // Generate column headers (A, B, C, ...)
  const columnHeaders = useMemo(() => {
    const headers: string[] = [];
    const maxCols = sheets[activeSheetIndex]?.cols || 0;
    for (let i = 0; i < maxCols; i++) {
      let header = '';
      let col = i;
      while (col >= 0) {
        header = String.fromCharCode(65 + (col % 26)) + header;
        col = Math.floor(col / 26) - 1;
      }
      headers.push(header);
    }
    return headers;
  }, [activeSheetIndex, sheets]);

  // Selected cell value
  const selectedCellValue = useMemo(() => {
    if (!cellSelection || !sheets[activeSheetIndex]) return null;
    const { row, col } = cellSelection;
    return sheets[activeSheetIndex].data[row]?.[col] ?? null;
  }, [cellSelection, activeSheetIndex, sheets]);

  if (loading) {
    return (
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center">
        <div className="text-zinc-400 font-mono text-sm">Excel yuklanmoqda...</div>
        <div className="mt-2 w-32 h-1 bg-zinc-800 rounded overflow-hidden">
          <div className="h-full bg-green-500 animate-pulse" style={{ width: '60%' }} />
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

  const activeSheet = sheets[activeSheetIndex];

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Sheet tabs */}
      <div className="flex items-center gap-1 px-2 py-1.5 bg-zinc-900 border-b border-zinc-800 shrink-0 overflow-x-auto">
        {sheets.map((sheet, index) => (
          <button
            key={sheet.name}
            onClick={() => setActiveSheetIndex(index)}
            className={`px-3 py-1 text-xs font-mono rounded transition-colors whitespace-nowrap ${
              index === activeSheetIndex
                ? 'bg-green-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            {sheet.name}
          </button>
        ))}
      </div>

      {/* Formula bar */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border-b border-zinc-800 shrink-0">
        <span className="text-xs font-mono text-zinc-500 w-16">
          {cellSelection
            ? `${columnHeaders[cellSelection.col]}${cellSelection.row + 1}`
            : '—'}
        </span>
        <span className="text-xs font-mono text-zinc-300 truncate flex-1">
          {selectedCellValue !== null ? formatCellValue(selectedCellValue) : ''}
        </span>
      </div>

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto bg-white">
        <table className="border-collapse text-xs font-mono">
          <thead className="sticky top-0 z-10">
            <tr>
              {/* Row number header */}
              <th className="bg-zinc-200 border border-zinc-300 px-2 py-1 text-zinc-500 font-normal sticky left-0 z-20">
                #
              </th>
              {/* Column headers */}
              {columnHeaders.map((header, i) => (
                <th
                  key={header}
                  className="bg-zinc-200 border border-zinc-300 px-2 py-1 text-zinc-600 font-normal"
                  style={{ minWidth: columnWidths[i] || 60 }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeSheet.data.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {/* Row number */}
                <td className="bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-zinc-500 text-right sticky left-0 z-10">
                  {rowIndex + 1}
                </td>
                {/* Cells */}
                {columnHeaders.map((_, colIndex) => {
                  const cellValue = row[colIndex];
                  const isSelected = cellSelection?.row === rowIndex && cellSelection?.col === colIndex;
                  const cellType = getCellType(cellValue);
                  
                  return (
                    <td
                      key={colIndex}
                      onClick={() => handleCellClick(rowIndex, colIndex)}
                      className={`border border-zinc-200 px-2 py-0.5 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-blue-100 outline outline-2 outline-blue-500'
                          : 'hover:bg-zinc-50'
                      } ${
                        cellType === 'number'
                          ? 'text-right text-blue-700'
                          : cellType === 'date'
                          ? 'text-purple-700'
                          : cellType === 'boolean'
                          ? 'text-center text-green-700'
                          : 'text-zinc-800'
                      }`}
                      style={{ minWidth: columnWidths[colIndex] || 60 }}
                    >
                      {formatCellValue(cellValue)}
                    </td>
                  );
                })}
                {/* Fill empty cells */}
                {Array.from({ length: Math.max(0, (activeSheet.cols || 26) - (row?.length || 0)) }).map((_, i) => (
                  <td
                    key={`empty-${i}`}
                    onClick={() => handleCellClick(rowIndex, (row?.length || 0) + i)}
                    className="border border-zinc-200 px-2 py-0.5 hover:bg-zinc-50"
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-t border-zinc-800 text-[10px] font-mono text-zinc-500 shrink-0">
        <span>
          {activeSheet.name} · {activeSheet.range}
        </span>
        <div className="flex items-center gap-3">
          <span>
            {activeSheet.rows} qator × {activeSheet.cols} ustun
            {selectedCellValue !== null && typeof selectedCellValue === 'number' && (
              <span className="ml-3 text-green-400">
                Sum: {activeSheet.data.flat().filter(v => typeof v === 'number').reduce((a, b) => a + b, 0).toFixed(2)}
              </span>
            )}
          </span>
          <button
            onClick={() => {
              // Export to CSV
              const csvContent = activeSheet.data
                .map(row => 
                  columnHeaders.map((_, colIndex) => {
                    const cellValue = row[colIndex] ?? '';
                    const cellStr = String(cellValue);
                    // Escape CSV values
                    if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
                      return `"${cellStr.replace(/"/g, '""')}"`;
                    }
                    return cellStr;
                  }).join(',')
                )
                .join('\n');
              
              const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `${activeSheet.name}.csv`;
              link.click();
              URL.revokeObjectURL(url);
            }}
            className="text-[10px] font-mono text-green-400 hover:text-green-300"
          >
            CSV ↓
          </button>
          <button
            onClick={() => {
              // Copy selected cell or all data
              if (cellSelection) {
                const cellValue = activeSheet.data[cellSelection.row]?.[cellSelection.col] ?? '';
                navigator.clipboard.writeText(String(cellValue));
              }
            }}
            disabled={!cellSelection}
            className="text-[10px] font-mono text-blue-400 hover:text-blue-300 disabled:opacity-30"
          >
            Nusxa olish
          </button>
        </div>
      </div>
    </div>
  );
}
