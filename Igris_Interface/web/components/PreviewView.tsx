import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { workspaceFileText } from '../backend';
import { LiveBuildView } from './LiveBuildView';
import { PDFViewer } from './PDFViewer';
import { SpreadsheetViewer } from './SpreadsheetViewer';
import { PowerPointViewer } from './PowerPointViewer';

// @ts-ignore - mammoth has no types
import * as mammoth from 'mammoth';

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i;
const UB_EXT = /\.uibuild\.json$/i;

// Office document extensions
const PDF_EXT = /\.pdf$/i;
const WORD_EXT = /\.docx?$/i;
const EXCEL_EXT = /\.xlsx?$/i;
const POWERPOINT_EXT = /\.pptx?$/i;
const OFFICE_EXT = /\.(docx?|xlsx?|pptx?)$/i;
const MARKDOWN_EXT = /\.md$/i;
const JSON_EXT = /\.json$/i;
const HTML_EXT = /\.html?$/i;
const CSS_EXT = /\.css$/i;
const JS_EXT = /\.js$/i;
const TS_EXT = /\.ts$/i;
const PY_EXT = /\.py$/i;
const CODE_EXT = /\.(js|ts|jsx|tsx|py|java|cpp|c|h|css|scss|less|html|htm|xml|json|yaml|yml|toml|ini|cfg|conf|sh|bash|zsh|fish|ps1|bat|cmd)$/i;

// File type detection
function getFileType(ext: string): string {
  if (PDF_EXT.test(ext)) return 'pdf';
  if (WORD_EXT.test(ext)) return 'word';
  if (EXCEL_EXT.test(ext)) return 'excel';
  if (POWERPOINT_EXT.test(ext)) return 'powerpoint';
  if (IMAGE_EXT.test(ext)) return 'image';
  if (UB_EXT.test(ext)) return 'uibuild';
  if (MARKDOWN_EXT.test(ext)) return 'markdown';
  if (JSON_EXT.test(ext)) return 'json';
  if (HTML_EXT.test(ext)) return 'html';
  if (CSS_EXT.test(ext)) return 'css';
  if (JS_EXT.test(ext)) return 'javascript';
  if (TS_EXT.test(ext)) return 'typescript';
  if (PY_EXT.test(ext)) return 'python';
  if (CODE_EXT.test(ext)) return 'code';
  return 'text';
}

// Part M (A7): juda katta fayllarda butun matnni render qilmaslik — re-render
// storm va xotira yukini cheklaydi (barcha qatorlar div bo'lib chizilmasin).
const TEXT_LINE_LIMIT = 500;

export function PreviewView() {
  const { selectedFile, pushDrawing } = useAgentConsoleStore();
  const taskRunning = useAgentConsoleStore((s) => s.taskRunning);
  const [fullLines, setFullLines] = useState<string[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(false);
  const [wordHtml, setWordHtml] = useState<string | null>(null);
  const [wordError, setWordError] = useState<string | null>(null);
  // Poll dedupe: kontent o'zgarmasa re-render yo'q.
  const lastContentRef = useRef<string | null>(null);

  const overLimit = (fullLines?.length ?? 0) > TEXT_LINE_LIMIT;
  const lines = fullLines && overLimit && !showAll
    ? fullLines.slice(0, TEXT_LINE_LIMIT)
    : fullLines;
  const isBinary = selectedFile.endsWith('.db') || selectedFile.endsWith('.bin');
  const isImage = IMAGE_EXT.test(selectedFile);
  const isBuildSpec = UB_EXT.test(selectedFile);
  const isPDF = PDF_EXT.test(selectedFile);
  const isWord = WORD_EXT.test(selectedFile);
  const isExcel = EXCEL_EXT.test(selectedFile);
  const isPowerPoint = POWERPOINT_EXT.test(selectedFile);
  const isOffice = OFFICE_EXT.test(selectedFile);
  const fileType = getFileType(selectedFile);
  
  // Office document preview URL (Microsoft Office Online Viewer)
  const officeViewerUrl = isOffice 
    ? `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(`file://${selectedFile}`)}`
    : '';

  // Word document conversion function
  const convertWordToHtml = useCallback(async (filePath: string) => {
    try {
      setWordError(null);
      setWordHtml(null);
      
      // Fetch the file as ArrayBuffer
      const response = await fetch(`file://${filePath}`);
      if (!response.ok) {
        // Try via workspace API
        const text = await workspaceFileText(filePath);
        // If we get text, it's not a binary docx
        throw new Error('File is not a valid DOCX');
      }
      
      const arrayBuffer = await response.arrayBuffer();
      
      // Convert using mammoth (without image conversion for simplicity)
      const result = await mammoth.convertToHtml(
        { arrayBuffer },
        {
          styleMap: [
            "p[style-name='Heading 1'] => h1:fresh",
            "p[style-name='Heading 2'] => h2:fresh",
            "p[style-name='Heading 3'] => h3:fresh",
            "p[style-name='Title'] => h1.title:fresh",
          ]
        }
      );
      
      setWordHtml(result.value);
      if (result.messages.length > 0) {
        console.warn('DOCX conversion warnings:', result.messages);
      }
    } catch (err) {
      setWordError(err instanceof Error ? err.message : 'Conversion failed');
    }
  }, []);
  
  // Real fayl kontentini Igris brain workspace'dan yuklash. Backend o'chiganda
  // — halol "preview yo'q" holat ko'rsatiladi (demo mock kontent yo'q).
  useEffect(() => {
    let cancelled = false;
    lastContentRef.current = null;
    setFullLines(null);
    setShowAll(false);
    setWordHtml(null);
    setWordError(null);
    
    if (!selectedFile || isImage || isBinary || isBuildSpec || isPDF) {
      setLoading(false);
      return;
    }
    
    // Handle Word documents with offline conversion
    if (isWord) {
      setLoading(true);
      convertWordToHtml(selectedFile).finally(() => {
        if (!cancelled) setLoading(false);
      });
      return () => { cancelled = true; };
    }
    
    setLoading(true);
    workspaceFileText(selectedFile)
      .then((text) => {
        if (cancelled) return;
        lastContentRef.current = text;
        setFullLines(text.split('\n'));
      })
      .catch(() => {
        // offline / topilmadi — bo'sh qoladi
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFile, isImage, isBinary, isBuildSpec, isWord, convertWordToHtml]);

  // TOKEN STREAM PREVIEW: agent/task ishlayotganda ochiq matn faylni JONLI
  // kuzatish — fayl yozilayotganda (agent write_file qilmoqda) kontent real
  // vaqtda yangilanadi (har ~2s). Fayl tugagach polling to'xtaydi, lekin
  // yangi task boshlansa yana davom etadi. Tab yashirilganda poll pauza.
  useEffect(() => {
    if (!taskRunning || !selectedFile || isImage || isBinary || isBuildSpec) return;
    const iv = setInterval(() => {
      if (document.hidden) return; // Part M (A7): ko'rinmas bo'lsa poll yo'q
      workspaceFileText(selectedFile)
        .then((text) => {
          // hash-dedupe — kontent o'zgarmasa re-render bo'lmaydi
          if (text === lastContentRef.current) return;
          lastContentRef.current = text;
          setFullLines(text.split('\n'));
        })
        .catch(() => {
          // fayl hali yozilmagan / offline — keyingi tikka davom etadi
        });
    }, 2000);
    return () => clearInterval(iv);
  }, [taskRunning, selectedFile, isImage, isBinary, isBuildSpec]);

  if (!selectedFile) {
    return (
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 shrink-0">
          <span className="font-mono text-xs text-zinc-400">preview</span>
        </div>
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="text-center space-y-2 max-w-sm">
            <div className="text-2xl">👁</div>
            <div className="text-sm font-ui text-zinc-300">Hech qanday fayl tanlanmagan</div>
            <div className="text-xs font-ui text-zinc-600 leading-relaxed">
              Workspace'dan fayl tanlang yoki agentga chizma/UI yaratishni so'rang —
              qurilish jarayoni shu oynada jonli ko'rinadi. (SVG elementma-element,
              UI spec qatlam-qatlam quriladi.)
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 shrink-0">
        <span className="font-mono text-xs text-zinc-400 truncate">{selectedFile}</span>
        <div className="flex items-center gap-2">
          {isOffice && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300 shrink-0">
              {isWord ? '📄 Word' : isExcel ? '📊 Excel' : isPowerPoint ? '📑 PowerPoint' : '📁 Office'}
            </span>
          )}
          {isPDF && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-900/50 text-red-300 shrink-0">
              📕 PDF
            </span>
          )}
          {(isImage || isBuildSpec) && (
            <span className="text-[10px] font-mono text-amber-400/90 shrink-0">
              LIVE BUILD · jarayonni kuzatish
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 overflow-auto px-4 py-3 font-mono text-xs leading-relaxed">
          {isBinary ? (
            <div className="text-zinc-600 font-ui">Binary file — no text preview available.</div>
          ) : isPDF ? (
            // PDF preview using PDF.js
            <PDFViewer filePath={selectedFile} />
          ) : isWord && wordHtml ? (
            // Word document offline preview (converted to HTML)
            <div className="flex-1 min-h-0 flex flex-col">
              <div className="flex-1 min-h-0 bg-white rounded-lg overflow-auto border border-zinc-800 p-6">
                <div 
                  className="prose prose-sm max-w-none text-gray-900"
                  dangerouslySetInnerHTML={{ __html: wordHtml }}
                  style={{
                    fontFamily: 'Calibri, Arial, sans-serif',
                    fontSize: '11pt',
                    lineHeight: '1.5',
                  }}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-mono text-zinc-500">
                  Word document · offline preview (mammoth.js)
                </span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      const blob = new Blob([wordHtml], { type: 'text/html' });
                      const url = URL.createObjectURL(blob);
                      window.open(url, '_blank');
                    }}
                    className="text-[10px] font-mono text-blue-400 hover:text-blue-300"
                  >
                    yangi oynada ochish →
                  </button>
                  <button
                    onClick={() => {
                      const blob = new Blob([wordHtml], { type: 'text/html' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = selectedFile.replace(/\.docx?$/i, '.html');
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="text-[10px] font-mono text-green-400 hover:text-green-300"
                  >
                    HTML yuklab olish ↓
                  </button>
                </div>
              </div>
            </div>
          ) : isWord && wordError ? (
            // Word document conversion error - fallback to online viewer
            <div className="flex-1 min-h-0 flex flex-col">
              <div className="flex-1 min-h-0 bg-zinc-950 rounded-lg overflow-hidden border border-zinc-800">
                <iframe
                  src={officeViewerUrl}
                  className="w-full h-full border-0"
                  title="Office Preview"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-mono text-amber-400">
                  ⚠️ Offline conversion failed — using online viewer
                </span>
                <div className="flex items-center gap-3">
                  <a
                    href={officeViewerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-mono text-blue-400 hover:text-blue-300"
                  >
                    to'liq ekran →
                  </a>
                </div>
              </div>
            </div>
          ) : isExcel ? (
            // Excel spreadsheet preview using SpreadsheetViewer
            <SpreadsheetViewer filePath={selectedFile} />
          ) : isOffice ? (
            // Other Office documents preview using Microsoft Office Online Viewer
            <div className="flex-1 min-h-0 flex flex-col">
              <div className="flex-1 min-h-0 bg-zinc-950 rounded-lg overflow-hidden border border-zinc-800">
                <iframe
                  src={officeViewerUrl}
                  className="w-full h-full border-0"
                  title="Office Preview"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-mono text-zinc-500">
                  {isExcel ? 'Excel' : isPowerPoint ? 'PowerPoint' : 'Office'} document preview
                </span>
                <div className="flex items-center gap-3">
                  <a
                    href={officeViewerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-mono text-blue-400 hover:text-blue-300"
                  >
                    to'liq ekran →
                  </a>
                  <a
                    href={`https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(`file://${selectedFile}`)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-mono text-green-400 hover:text-green-300"
                  >
                    Microsoft'da ochish →
                  </a>
                </div>
              </div>
            </div>
          ) : isPowerPoint ? (
            // PowerPoint preview using PowerPointViewer
            <PowerPointViewer filePath={selectedFile} />
          ) : isImage || isBuildSpec ? (
            <div className="flex-1 min-h-0 flex">
              <LiveBuildView
                path={selectedFile}
                onEdited={(p) => pushDrawing(p, '✎ safe-freeze tahriri qo\'llandi — chatda yangi versiyani tomosha qilish mumkin')}
              />
            </div>
          ) : loading && !lines ? (
            <div className="text-zinc-600 font-ui">// loading from workspace…</div>
          ) : lines ? (
            <>
              {lines.map((l, i) => (
                <div key={i} className="flex gap-3 text-zinc-300 hover:bg-zinc-900 px-1.5 rounded">
                  <span className="text-zinc-700 select-none w-5 text-right shrink-0">{i + 1}</span>
                  <span className="whitespace-pre">{l || ' '}</span>
                </div>
              ))}
              {overLimit && !showAll && (
                <button
                  onClick={() => setShowAll(true)}
                  className="text-[11px] font-mono text-sky-400/80 hover:text-sky-300 px-1.5 py-1 mt-1"
                >
                  … yana {fullLines!.length - TEXT_LINE_LIMIT} satr bor · hammasini ko'rsatish
                </button>
              )}
            </>
          ) : (
            <div className="text-zinc-600 font-ui">
              // no preview available — fayl workspace'da topilmadi yoki backend offline
            </div>
          )}
        </div>
      </div>
      <div className="px-4 py-1.5 border-t border-zinc-800 text-[10px] font-mono text-zinc-600 shrink-0">
        {isImage || isBuildSpec ? (
          <>live build · real qurilish — element/qatlamlar navbatma-navbat; tugallangan qismlar darhol ishlaydi</>
        ) : isPDF ? (
          <>PDF.js viewer · offline rendering · sahifalar va zoom boshqaruv</>
        ) : isWord && wordHtml ? (
          <>Word document · offline preview (mammoth.js) · HTML formatga konvertatsiya qilindi</>
        ) : isWord && wordError ? (
          <>Word document · offline conversion failed · online viewer ishlatilmoqda</>
        ) : isExcel ? (
          <>Excel spreadsheet · offline viewer (xlsx.js) · jadvallar va formulalar</>
        ) : isPowerPoint ? (
          <>PowerPoint · offline viewer (pptx.js) · slayd navigatsiya</>
        ) : isOffice ? (
          <>Office document · Microsoft Office Online Viewer orqali ko'rsatilmoqda</>
        ) : taskRunning && !isBinary ? (
          <><span className="text-amber-400 animate-pulse">●</span> live kuzatish — agent faylni yozmoqda, kontent real vaqtda yangilanadi</>
        ) : fullLines ? (
          <>live workspace file · fetched from Igris brain</>
        ) : (
          <>offline · <span className="text-amber-500">python server.py</span> ishga tushirilsa real workspace preview ochiladi</>
        )}
      </div>
    </div>
  );
}
