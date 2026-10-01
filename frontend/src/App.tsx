import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { DocumentPanel } from './components/DocumentPanel';
import { useStore } from './store';
import { Menu, FileText, Sun, Moon } from 'lucide-react';

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { fetchSessions, theme, setTheme, pdfOpen, setPdfOpen, sessions, activeSessionId } = useStore();
  const session = sessions.find(s => s.id === activeSessionId);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  return (
    <div className={`${theme} flex flex-col h-screen w-full overflow-hidden bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-300`}>
      {/* GLOBAL UNIFIED HEADER */}
      <header className="h-16 shrink-0 flex items-center justify-between px-4 z-30 bg-[var(--bg-secondary)] shadow-sm">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)} 
            className="p-2 hover:bg-[var(--bg-tertiary)] rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors bg-transparent border-none cursor-pointer"
          >
            <Menu size={22} />
          </button>
          <h2 className="font-bold text-xl tracking-tight text-[var(--accent-color)]">Legal RAG</h2>
          {session && (
            <>
              <div className="w-px h-6 bg-[var(--border-color)] hidden sm:block mx-1"></div>
              <h3 className="font-medium text-[var(--text-secondary)] hidden sm:block">{session.title}</h3>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="p-2.5 hover:bg-[var(--bg-tertiary)] rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors flex items-center justify-center bg-transparent border-none cursor-pointer"
            title="Toggle Theme"
          >
            {theme === 'dark' ? <Sun size={22} /> : <Moon size={22} />}
          </button>
          <button 
            onClick={() => setPdfOpen(!pdfOpen)}
            className={`p-2.5 rounded-xl transition-colors flex items-center justify-center border-none cursor-pointer ${pdfOpen ? 'bg-[var(--text-primary)] text-[var(--bg-primary)] hover:opacity-90' : 'bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'}`}
            title="Toggle PDF Viewer"
          >
            <FileText size={22} />
          </button>
        </div>
      </header>

      {/* MAIN PANELS AREA */}
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar isOpen={sidebarOpen} />
        
        <ChatPanel />
        
        <DocumentPanel />
      </div>
    </div>
  );
}
