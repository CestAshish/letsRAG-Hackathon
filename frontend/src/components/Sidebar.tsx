import React from 'react';
import { useStore } from '../store';
import { MessageSquare, Plus, X, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';

export function Sidebar({ isOpen }: { isOpen: boolean }) {
  const { sessions, activeSessionId, createSession, setActiveSession, deleteSession } = useStore();

  return (
    <div className={clsx(
      "h-full bg-[var(--bg-secondary)] transition-all duration-300 flex flex-col z-20 shrink-0 shadow-sm",
      isOpen ? "w-64" : "w-0 overflow-hidden"
    )}>
      
      <div className="p-4">
        <button 
          onClick={createSession}
          className="w-full flex items-center gap-2 bg-[var(--accent-color)] text-white hover:bg-[var(--accent-hover)] p-2.5 rounded-lg transition-colors font-medium whitespace-nowrap shadow-sm border-none cursor-pointer"
        >
          <Plus size={20} /> New Chat
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessions.map(s => (
          <div key={s.id} className={clsx(
            "group flex items-center w-full p-2 rounded-lg transition-colors text-sm",
            activeSessionId === s.id ? "bg-[var(--bg-tertiary)] text-[var(--text-primary)] font-medium" : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
          )}>
            <button
              onClick={() => setActiveSession(s.id)}
              className="flex-1 flex items-center gap-3 text-left overflow-hidden bg-transparent border-none cursor-pointer"
            >
              <MessageSquare size={16} className="shrink-0" />
              <span className="truncate">{s.title}</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(s.id);
              }}
              className="p-1 text-[var(--text-secondary)] opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all rounded bg-transparent border-none cursor-pointer"
              title="Delete Chat"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
