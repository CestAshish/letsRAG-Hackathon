import { create } from 'zustand';
import axios from 'axios';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  trajectory?: any[];
  message_id_ref?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

interface AppState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  activeHighlights: Array<{ page: number; bbox: number[] }> | null;
  theme: 'light' | 'dark';
  pdfOpen: boolean;
  
  createSession: () => void;
  setActiveSession: (id: string) => Promise<void>;
  fetchSessions: () => Promise<void>;
  addMessage: (sessionId: string, message: Message) => void;
  setActiveHighlights: (highlights: Array<{ page: number; bbox: number[] }>) => void;
  deleteSession: (id: string) => Promise<void>;
  setTheme: (theme: 'light' | 'dark') => void;
  setPdfOpen: (open: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  sessions: [],
  activeSessionId: null,
  activeHighlights: null,
  theme: 'light',
  pdfOpen: false,
  
  createSession: () => set((state) => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: 'New Chat',
      messages: []
    };
    return {
      sessions: [newSession, ...state.sessions],
      activeSessionId: newSession.id
    };
  }),
  
  setActiveSession: async (id) => {
    set({ activeSessionId: id, activeHighlights: null });
    try {
      const res = await axios.get(`http://localhost:8000/api/chat/${id}`);
      if (res.data.messages && res.data.messages.length > 0) {
        set((state) => {
          const sessions = [...state.sessions];
          const idx = sessions.findIndex(s => s.id === id);
          if (idx >= 0) {
            sessions[idx].messages = res.data.messages;
            sessions[idx].title = res.data.messages[0].content.substring(0, 30) + '...';
          } else {
             // Handle case where we click a session we haven't created in local state yet
             sessions.push({
               id,
               title: res.data.messages[0].content.substring(0, 30) + '...',
               messages: res.data.messages
             });
          }
          return { sessions };
        });
      }
    } catch (e) {
      console.error("Failed to load session from backend", e);
    }
  },
  
  fetchSessions: async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/sessions');
      if (res.data.sessions) {
        set((state) => {
          const loadedSessions = res.data.sessions.map((s: any) => {
            // Keep local messages if already loaded, else start empty
            const existing = state.sessions.find(es => es.id === s.id);
            return {
              id: s.id,
              title: s.title,
              messages: existing ? existing.messages : []
            };
          });
          return { sessions: loadedSessions };
        });
        
        // If no active session, open the most recent one
        const currentState = useStore.getState();
        if (!currentState.activeSessionId && res.data.sessions.length > 0) {
          currentState.setActiveSession(res.data.sessions[0].id);
        } else if (res.data.sessions.length === 0 && !currentState.activeSessionId) {
          currentState.createSession();
        }
      }
    } catch (e) {
      console.error("Failed to fetch sessions list", e);
    }
  },
  
  addMessage: (sessionId, message) => set((state) => {
    const updatedSessions = state.sessions.map(s => {
      if (s.id === sessionId) {
        // Auto-title on first message
        const title = s.messages.length === 0 ? message.content.substring(0, 30) + '...' : s.title;
        return { ...s, title, messages: [...s.messages, message] };
      }
      return s;
    });
    return { sessions: updatedSessions };
  }),
  
  setActiveHighlights: (highlights) => set({ activeHighlights: highlights }),

  deleteSession: async (id) => {
    try {
      await axios.delete(`http://localhost:8000/api/sessions/${id}`);
      set((state) => {
        const sessions = state.sessions.filter(s => s.id !== id);
        let activeSessionId = state.activeSessionId;
        if (activeSessionId === id) {
          activeSessionId = sessions.length > 0 ? sessions[0].id : null;
        }
        // If we deleted the last session, optionally create a new one
        if (sessions.length === 0) {
          setTimeout(() => useStore.getState().createSession(), 0);
        } else if (activeSessionId && activeSessionId !== state.activeSessionId) {
          setTimeout(() => useStore.getState().setActiveSession(activeSessionId!), 0);
        }
        return { sessions, activeSessionId };
      });
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  },
  
  setTheme: (theme) => set({ theme }),
  setPdfOpen: (pdfOpen) => set({ pdfOpen })
}));
