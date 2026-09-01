import React, { useState, useEffect, useCallback, useRef } from 'react';
import JSZip from 'jszip';

interface PowerPointViewerProps {
  filePath: string;
  onError?: (error: string) => void;
}

interface SlideData {
  index: number;
  title: string;
  content: string;
  notes: string;
  html: string;
}

export function PowerPointViewer({ filePath, onError }: PowerPointViewerProps) {
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [thumbnails, setThumbnails] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Parse PPTX file
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const parsePPTX = async () => {
      try {
        const response = await fetch(`file://${filePath}`);
        if (!response.ok) throw new Error('Failed to fetch PPTX file');
        
        const arrayBuffer = await response.arrayBuffer();
        const zip = await JSZip.loadAsync(arrayBuffer);
        
        // Find slide files
        const slideFiles: string[] = [];
        zip.forEach((path) => {
          if (path.match(/^ppt\/slides\/slide\d+\.xml$/)) {
            slideFiles.push(path);
          }
        });
        
        slideFiles.sort((a, b) => {
          const numA = parseInt(a.match(/slide(\d+)\.xml/)?.[1] || '0');
          const numB = parseInt(b.match(/slide(\d+)\.xml/)?.[1] || '0');
          return numA - numB;
        });
        
        const parsedSlides: SlideData[] = [];
        
        for (const slideFile of slideFiles) {
          const xml = await zip.file(slideFile)?.async('string');
          if (!xml) continue;
          
          // Extract text content from XML
          const titleMatch = xml.match(/<a:t>([^<]+)<\/a:t>/g);
          const texts = titleMatch?.map(t => t.replace(/<\/?a:t>/g, '')) || [];
          
          // Extract notes
          const notesMatch = xml.match(/<p:notes[^>]*>([\s\S]*?)<\/p:notes>/);
          const notes = notesMatch?.[1]?.replace(/<[^>]+>/g, '').trim() || '';
          
          // Create HTML representation
          const html = `
            <div style="padding: 40px; min-height: 100%; display: flex; flex-direction: column; justify-content: center;">
              ${texts.map((text, i) => `
                <div style="margin-bottom: ${i === 0 ? '20px' : '10px'}; font-size: ${i === 0 ? '28px' : '18px'}; font-weight: ${i === 0 ? 'bold' : 'normal'}; color: ${i === 0 ? '#1a1a1a' : '#333'};">
                  ${text}
                </div>
              `).join('')}
              ${texts.length === 0 ? '<div style="color: #999; font-style: italic;">Bo\'sh slayd</div>' : ''}
            </div>
          `;
          
          parsedSlides.push({
            index: parsedSlides.length,
            title: texts[0] || `Slayd ${parsedSlides.length + 1}`,
            content: texts.slice(1).join(' '),
            notes,
            html,
          });
        }
        
        if (!cancelled) {
          setSlides(parsedSlides);
          setCurrentSlide(0);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to parse PPTX';
          setError(errorMsg);
          onError?.(errorMsg);
          setLoading(false);
        }
      }
    };

    parsePPTX();
    return () => { cancelled = true; };
  }, [filePath, onError]);

  // Navigation
  const goToSlide = useCallback((index: number) => {
    if (index >= 0 && index < slides.length) {
      setCurrentSlide(index);
    }
  }, [slides.length]);

  const prevSlide = useCallback(() => goToSlide(currentSlide - 1), [currentSlide, goToSlide]);
  const nextSlide = useCallback(() => goToSlide(currentSlide + 1), [currentSlide, goToSlide]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault();
        prevSlide();
      } else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        e.preventDefault();
        nextSlide();
      } else if (e.key === 'Home') {
        e.preventDefault();
        goToSlide(0);
      } else if (e.key === 'End') {
        e.preventDefault();
        goToSlide(slides.length - 1);
      } else if (e.key === 't' || e.key === 'T') {
        e.preventDefault();
        setThumbnails(t => !t);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [prevSlide, nextSlide, goToSlide, slides.length]);

  if (loading) {
    return (
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center">
        <div className="text-zinc-400 font-mono text-sm">PowerPoint yuklanmoqda...</div>
        <div className="mt-2 w-32 h-1 bg-zinc-800 rounded overflow-hidden">
          <div className="h-full bg-orange-500 animate-pulse" style={{ width: '60%' }} />
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

  const slide = slides[currentSlide];

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Controls */}
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={prevSlide}
            disabled={currentSlide <= 0}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            ←
          </button>
          <span className="text-xs font-mono text-zinc-400">
            {currentSlide + 1} / {slides.length}
          </span>
          <button
            onClick={nextSlide}
            disabled={currentSlide >= slides.length - 1}
            className="px-2 py-1 text-xs font-mono bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed rounded"
          >
            →
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setThumbnails(t => !t)}
            className={`px-2 py-1 text-xs font-mono rounded ${
              thumbnails ? 'bg-orange-600 text-white' : 'bg-zinc-800 hover:bg-zinc-700'
            }`}
          >
            {thumbnails ? '📋' : '📋'} Thumbnails
          </button>
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

      {/* Thumbnail strip */}
      {thumbnails && (
        <div className="flex gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800 overflow-x-auto shrink-0">
          {slides.map((s, i) => (
            <button
              key={i}
              onClick={() => goToSlide(i)}
              className={`flex-shrink-0 w-32 h-20 rounded border-2 overflow-hidden transition-all ${
                i === currentSlide
                  ? 'border-orange-500 shadow-lg shadow-orange-500/20'
                  : 'border-zinc-700 hover:border-zinc-500'
              }`}
            >
              <div 
                className="w-full h-full bg-white text-zinc-800 text-[8px] p-1 overflow-hidden"
                dangerouslySetInnerHTML={{ __html: s.html }}
              />
            </button>
          ))}
        </div>
      )}

      {/* Main slide */}
      <div 
        ref={containerRef}
        className="flex-1 min-h-0 overflow-auto bg-zinc-950 flex items-center justify-center p-8"
      >
        <div 
          className="w-full max-w-4xl bg-white rounded-lg shadow-2xl overflow-hidden"
          style={{ aspectRatio: '16/9' }}
        >
          <div 
            className="w-full h-full"
            dangerouslySetInnerHTML={{ __html: slide?.html || '' }}
          />
        </div>
      </div>

      {/* Slide info */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-t border-zinc-800 text-[10px] font-mono text-zinc-500 shrink-0">
        <span>{slide?.title || 'Slayd'}</span>
        <span>
          {currentSlide + 1} / {slides.length} · 
          {slide?.notes && ' ✏️ Notes mavjud'}
        </span>
      </div>
    </div>
  );
}
