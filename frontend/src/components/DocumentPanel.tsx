import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { X } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { useStore } from '../store';

// Set up the worker for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

/**
 * PyMuPDF extracts bounding boxes in native PDF points (72 DPI).
 * react-pdf at scale=1.0 renders exactly 1 PDF point to 1 CSS pixel.
 * Scale factor: 1.0
 */
const PDF_TO_CSS_SCALE = 1.0;

export function DocumentPanel() {
  const { activeHighlights, setPdfOpen, pdfOpen } = useStore();
  const [numPages, setNumPages] = useState<number>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Jump to first highlighted page when highlights change or panel opens
  useEffect(() => {
    if (pdfOpen && activeHighlights && activeHighlights.length > 0) {
      // Small timeout ensures the panel has transitioned from w-0 to visible
      // so scroll calculations work correctly.
      setTimeout(() => {
        const firstPage = [...activeHighlights].sort((a, b) => a.page - b.page)[0].page;
        const pageElement = document.getElementById(`pdf-page-${firstPage}`);
        if (pageElement) {
          pageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 150);
    }
  }, [activeHighlights, pdfOpen, numPages]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }): void {
    setNumPages(numPages);
  }

  const renderHighlight = (pageIndex: number) => {
    if (!activeHighlights || activeHighlights.length === 0) return null;
    
    const highlightsOnThisPage = activeHighlights.filter(h => h.page === pageIndex);
    if (highlightsOnThisPage.length === 0) return null;

    return highlightsOnThisPage.map((highlight, idx) => {
      const [x0, y0, x1, y1] = highlight.bbox;
      
      // Apply DPI scaling from PDF points to CSS pixels
      const left = x0 * PDF_TO_CSS_SCALE;
      const top = y0 * PDF_TO_CSS_SCALE;
      const width = (x1 - x0) * PDF_TO_CSS_SCALE;
      const height = (y1 - y0) * PDF_TO_CSS_SCALE;
      
      return (
        <div 
          key={idx}
          className="absolute bg-[var(--accent-color)] opacity-40 border-2 border-[var(--accent-hover)] rounded pointer-events-none"
          style={{
            left: `${left}px`,
            top: `${top}px`,
            width: `${width}px`,
            height: `${height}px`,
            zIndex: 50,
            animation: 'pulse 2s ease-in-out 3'
          }}
        />
      );
    });
  };

  return (
    <div className={`bg-[var(--bg-tertiary)] flex flex-col h-full overflow-hidden relative transition-all duration-300 ${pdfOpen ? 'flex-1 min-w-[500px]' : 'w-0 min-w-0 border-none'}`}>
      {/* PDF Canvas - Continuous Scroll */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto p-8 flex flex-col items-center bg-[var(--bg-primary)] gap-8"
      >
        <Document 
          file="/EU_AI_Act.pdf" 
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="w-[600px] h-[800px] flex items-center justify-center text-[var(--text-secondary)] bg-[var(--bg-secondary)] shadow-sm">
              Loading Document...
            </div>
          }
        >
          {Array.from(new Array(numPages || 0), (el, index) => (
            <div id={`pdf-page-${index + 1}`} key={`page_${index + 1}`} className="relative shadow-2xl bg-[var(--bg-secondary)] mb-8">
              <Page 
                pageNumber={index + 1} 
                renderTextLayer={true}
                renderAnnotationLayer={true}
                scale={1.0}
                loading={
                  <div className="w-[595px] h-[842px] flex items-center justify-center text-[var(--text-secondary)] bg-[var(--bg-tertiary)]">
                    Loading page {index + 1}...
                  </div>
                }
              />
              {renderHighlight(index + 1)}
            </div>
          ))}
        </Document>
      </div>
    </div>
  );
}
