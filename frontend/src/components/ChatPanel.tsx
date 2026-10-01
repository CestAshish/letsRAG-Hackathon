import React, { useState, useRef, useEffect } from 'react';
import { useStore } from '../store';
import { ArrowUp, Activity, CheckCircle, FileText } from 'lucide-react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { TelemetryModal } from './TelemetryModal';

interface LineInfo {
  num: number;
  text: string;
  bbox: number[];
  page: number;
}

interface SourceInfo {
  page: number;
  bbox: number[];
  parent_heading: string;
  lines: LineInfo[];
  text: string;
  node_path?: string[];
}

export function ChatPanel() {
  const { sessions, activeSessionId, addMessage, setActiveHighlights, theme, setTheme, pdfOpen, setPdfOpen } = useStore();
  const [input, setInput] = useState('');
  const [loadingSessions, setLoadingSessions] = useState<Set<string>>(new Set());
  const [telemetryMessageId, setTelemetryMessageId] = useState<string | null>(null);
  const [lastSources, setLastSources] = useState<SourceInfo[]>([]);
  const [webhookStatus, setWebhookStatus] = useState<Record<string, string>>({});
  const [wizardState, setWizardState] = useState<Record<string, { current: number, answers: {q: string, a: string}[] }>>({});
  const [wizardInput, setWizardInput] = useState('');
  const [handledWebhooks, setHandledWebhooks] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem('handled_webhooks') || '[]')); }
    catch { return new Set(); }
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const session = sessions.find(s => s.id === activeSessionId);

  const handleWizardAnswer = (msgId: string, allQuestions: string[], question: string, answer: string) => {
    const currentW = wizardState[msgId] || { current: 0, answers: [] };
    const newAnswers = [...currentW.answers, { q: question, a: answer }];
    const newCurrent = currentW.current + 1;
    
    // 1. Update state cleanly (pure function)
    setWizardState(prev => ({
      ...prev,
      [msgId]: { current: newCurrent, answers: newAnswers }
    }));
    
    // 2. Run side effects exactly once per click, OUTSIDE the setter
    if (newCurrent >= allQuestions.length) {
      markWebhookHandled(msgId);
      const summary = newAnswers.map((ans, i) => `${i+1}. [${ans.a}] ${ans.q}`).join('\n');
      const autoReply = `Here are the answers to the risk assessment wizard:\n\n${summary}\n\nPlease analyze this, determine my final risk classification, and use the create_pdf_summary tool to generate a formal Risk Classification Report.`;
      setTimeout(() => handleSend(autoReply), 100);
    }
  };

  const markWebhookHandled = (msgId: string) => {
    setHandledWebhooks(prev => {
      const next = new Set(prev);
      next.add(msgId);
      localStorage.setItem('handled_webhooks', JSON.stringify(Array.from(next)));
      return next;
    });
  };

  const handleConfirmWebhook = async (msgId: string, payload: string) => {
    markWebhookHandled(msgId);
    setWebhookStatus(prev => ({...prev, [msgId]: 'sending'}));
    try {
      await axios.post('http://localhost:8000/api/send_webhook', { message: payload });
      setWebhookStatus(prev => ({...prev, [msgId]: 'sent'}));
      setTimeout(() => {
        setWebhookStatus(prev => ({...prev, [msgId]: 'hidden'}));
      }, 3000);
    } catch (e) {
      setWebhookStatus(prev => ({...prev, [msgId]: 'error'}));
      setTimeout(() => {
        setWebhookStatus(prev => ({...prev, [msgId]: 'hidden'}));
      }, 3000);
    }
  };

  const handleCancelWebhook = (msgId: string) => {
    markWebhookHandled(msgId);
    setWebhookStatus(prev => ({...prev, [msgId]: 'hidden'}));
  };

  const [liveStatus, setLiveStatus] = useState('Thinking...');

  const isLoadingCurrentSession = activeSessionId ? loadingSessions.has(activeSessionId) : false;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages.length, isLoadingCurrentSession]);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoadingCurrentSession && activeSessionId) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`http://localhost:8000/api/status/${activeSessionId}`);
          if (res.data && res.data.status) setLiveStatus(res.data.status);
        } catch (e) {
          // ignore polling errors
        }
      }, 500);
    } else {
      setLiveStatus('Thinking...');
    }
    return () => clearInterval(interval);
  }, [isLoadingCurrentSession, activeSessionId]);

  /**
   * Resolves a [Chunk X, Lines Y-Z] citation to precise bboxes.
   * Looks up the chunk's lines metadata and extracts the bboxes for lines Y through Z.
   */
  const resolveChunkCitation = (chunkIdx: number, lineStart: number, lineEnd: number, sources: SourceInfo[]) => {
    if (chunkIdx < 0 || chunkIdx >= sources.length) return;
    
    const source = sources[chunkIdx];
    const lines = source.lines || [];
    
    // Find the matching lines
    const matchedLines = lines.filter(l => l.num >= lineStart && l.num <= lineEnd);
    
    if (matchedLines.length > 0) {
      // Group lines by page
      const pageGroups: Record<number, any[]> = {};
      matchedLines.forEach(l => {
        if (!pageGroups[l.page]) pageGroups[l.page] = [];
        pageGroups[l.page].push(l);
      });
      
      const highlights: Array<{ page: number; bbox: number[] }> = [];
      
      for (const [pageStr, linesOnPage] of Object.entries(pageGroups)) {
        const page = parseInt(pageStr);
        // Filter out headers/footers which distort the bounding box (y < 60 or y > 800)
        const contentLines = linesOnPage.filter(l => l.bbox[1] > 60 && l.bbox[3] < 800);
        const validLines = contentLines.length > 0 ? contentLines : linesOnPage;
        
        const bboxes = validLines.map(l => l.bbox);
        const unionBbox = [
          Math.min(...bboxes.map(b => b[0])),
          Math.min(...bboxes.map(b => b[1])),
          Math.max(...bboxes.map(b => b[2])),
          Math.max(...bboxes.map(b => b[3])),
        ];
        
        highlights.push({ page, bbox: unionBbox });
      }
      
      useStore.getState().setActiveHighlights(highlights);
    } else {
      // Fallback to chunk-level bbox
      useStore.getState().setActiveHighlights([{ page: source.page, bbox: source.bbox }]);
    }
  };

  // Parse [Chunk X, Lines Y-Z] or [Chunk X] citations and legacy [Page X, BBOX: ...]
  const renderMessageContent = (text: string, sources: SourceInfo[]) => {
    // Made highly permissive to catch any zero-width spaces or weird dashes. Lines are optional.
    const regex = /\[.*?Chunk\s*(\d+)(?:.*?Line[s]?\s*(\d+)(?:.*?(\d+))?)?.*?\]|\[\s*Page\s+(\d+),\s*BBOX:\s*([\d\.,\s]+)\s*\]/gi;
    
    const citations: Array<{ chunkIdx: number, lineStart: number, lineEnd: number, bbox?: number[], page?: number }> = [];
    const seenChunks = new Set<number>();
    
    // Strip all citations from text
    let cleanText = text;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match[1]) {
        const chunkIdx = parseInt(match[1]) - 1;
        if (!seenChunks.has(chunkIdx)) {
          seenChunks.add(chunkIdx);
          const lineStart = parseInt(match[2]);
          const lineEnd = match[3] ? parseInt(match[3]) : lineStart;
          citations.push({ chunkIdx, lineStart, lineEnd });
        }
      } else if (match[4]) {
        const page = parseInt(match[4]);
        const bbox = match[5].split(',').map((s: string) => parseFloat(s.trim()));
        citations.push({ chunkIdx: -1, lineStart: 1, lineEnd: 1, bbox, page });
      }
    }
    
    cleanText = cleanText.replace(regex, '').trim();
    
    return (
      <div className="flex flex-col">
        <div className="whitespace-pre-wrap leading-relaxed prose prose-sm max-w-none text-[var(--text-primary)] prose-table:border-collapse prose-table:w-full prose-table:my-4 prose-th:border prose-th:border-[var(--border-color)] prose-th:bg-[var(--bg-tertiary)] prose-th:px-3 prose-th:py-2 prose-td:border prose-td:border-[var(--border-color)] prose-td:px-3 prose-td:py-2 dark:prose-invert">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({node, ...props}) => {
                if (props.href?.startsWith('#chunk-')) {
                  const chunkStr = props.href.replace('#chunk-', '');
                  let chunkIdx = parseInt(chunkStr) - 1;
                  // Handle edge case where LLM gives comma separated lists in one link
                  if (isNaN(chunkIdx) || chunkIdx < 0 || chunkIdx >= sources.length) {
                    return <span className="text-gray-500 font-semibold" title="Missing source chunk" style={{marginRight: '4px'}}>{props.children}</span>;
                  }
                  return (
                    <a
                      href={`#chunk-${chunkIdx+1}`}
                      onClick={(e) => {
                        e.preventDefault();
                        resolveChunkCitation(chunkIdx, 1, 9999, sources);
                        useStore.getState().setPdfOpen(true);
                      }}
                      className="inline text-blue-600 dark:text-blue-400 font-semibold hover:text-blue-800 dark:hover:text-blue-300 hover:underline cursor-pointer transition-colors"
                      style={{marginRight: '6px'}}
                    >
                      {props.children}
                    </a>
                  );
                }
                return <a {...props} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline" />;
              }
            }}
          >
            {cleanText}
          </ReactMarkdown>
        </div>
        {citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-700/50 flex flex-wrap gap-2">
            {citations.map((cit, idx) => {
              let label = "View Source Document";
              if (cit.chunkIdx !== -1 && sources[cit.chunkIdx]) {
                const nodePath = sources[cit.chunkIdx].node_path || [];
                if (nodePath.length > 0) {
                  label = nodePath[nodePath.length - 1].split(' - ')[0]; // e.g., "Article 51"
                } else if ((sources[cit.chunkIdx] as any).parent_heading) {
                  label = (sources[cit.chunkIdx] as any).parent_heading.split(' - ')[0];
                } else {
                  label = `Source ${idx + 1}`;
                }
              }
              
              return (
                <button 
                  key={idx}
                  onClick={() => {
                    if (cit.chunkIdx !== -1) {
                      resolveChunkCitation(
                        cit.chunkIdx, 
                        isNaN(cit.lineStart) ? 1 : cit.lineStart, 
                        isNaN(cit.lineStart) ? 9999 : cit.lineEnd, 
                        sources
                      );
                      useStore.getState().setPdfOpen(true);
                    } else if (cit.bbox) {
                      useStore.getState().setActiveHighlights([{ page: cit.page!, bbox: cit.bbox! }]);
                      useStore.getState().setPdfOpen(true);
                    }
                  }}
                  className="inline-flex items-center gap-1.5 bg-[#fef08a] text-black px-3 py-1.5 rounded-md text-xs font-semibold hover:bg-[#fde047] transition-colors border border-[#fde047] shadow-sm"
                >
                  <FileText size={14} />
                  {label}
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const handleSend = async (overrideInput?: string) => {
    const userContent = typeof overrideInput === 'string' ? overrideInput : input.trim();
    if (!userContent || !activeSessionId || !session) return;
    
    const targetSessionId = activeSessionId;
    
    if (typeof overrideInput !== 'string') setInput('');

    const messageId = Date.now().toString();
    const userMsg = { id: messageId, role: 'user' as const, content: userContent };
    addMessage(targetSessionId, userMsg);
    
    setLoadingSessions(prev => {
      const next = new Set(prev);
      next.add(targetSessionId);
      return next;
    });
    
    try {
      const res = await axios.post('http://localhost:8000/api/chat', { 
        query: userContent,
        session_id: targetSessionId,
        message_id: messageId
      });
      
      const sources: SourceInfo[] = res.data.sources || [];
      const trajectory = res.data.trajectory || [];
      setLastSources(sources);
      
      addMessage(targetSessionId, {
        id: messageId + "_reply",
        role: 'assistant',
        content: res.data.answer,
        sources: sources,
        trajectory: trajectory,
        message_id_ref: messageId
      });
    } catch (e) {
      addMessage(targetSessionId, { 
        id: Date.now().toString() + "_error", 
        role: 'assistant', 
        content: 'I encountered an error connecting to the backend. Please try again in a moment.' 
      });
    }
    
    setLoadingSessions(prev => {
      const next = new Set(prev);
      next.delete(targetSessionId);
      return next;
    });
  };

  if (!activeSessionId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white border-r border-gray-200">
        <p className="text-gray-400">Select or create a chat to begin.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-[var(--bg-primary)] min-w-[400px] transition-colors h-full relative">
      <div className="flex-1 overflow-y-auto pb-32 no-scrollbar w-full">
        <div className="max-w-3xl mx-auto w-full px-4 pt-6 space-y-8 min-h-full flex flex-col">
          {(!session?.messages || session.messages.length === 0) && !isLoadingCurrentSession ? (
            <div className="flex-1 flex flex-col justify-end pb-8 w-full mx-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
                {[
                  "What is Article 51?",
                  "What are the guidelines for implementation of the regulation?",
                  "What are the guidelines for AI use for minors?",
                  "Summarize the criteria for high-risk AI systems."
                ].map((suggestion, idx) => (
                  <button 
                    key={idx}
                    onClick={() => { setInput(suggestion); handleSend(suggestion); }}
                    className="p-4 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-2xl text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] hover:border-[var(--accent-color)] transition-all cursor-pointer shadow-sm w-full font-medium"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {session?.messages.map(m => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex flex-col gap-2 max-w-[85%]`}>
              {m.trajectory && m.trajectory.length > 0 && (
                <div className="flex flex-col gap-1 mt-1 text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-secondary)] rounded-lg p-2 border border-[var(--border-color)] shadow-sm self-start">
                  <div className="font-semibold text-[var(--text-primary)] mb-1 border-b border-[var(--border-color)] pb-1">Agent Action Trace</div>
                  {m.trajectory.map((step: any, i: number) => {
                    let displayArgs = JSON.stringify(step.args);
                    if (step.tool === 'create_pdf_summary' || step.tool === 'send_message') {
                      displayArgs = '{ ... large content hidden ... }';
                    }
                    return (
                      <div key={i} className="truncate whitespace-normal">
                        <span className="text-[var(--accent-color)]">[{i+1}] {step.tool}</span>: <span className="text-[var(--text-secondary)]">{displayArgs}</span>
                      </div>
                    );
                  })}
                </div>
              )}
              {m.role === 'user' && m.content.startsWith('Here are the answers to the risk assessment wizard:') ? (
                <div className="bg-purple-100 border border-purple-200 text-purple-800 rounded-xl px-4 py-2.5 shadow-sm text-sm font-medium flex items-center gap-2">
                  <CheckCircle size={16} className="text-purple-600" />
                  Risk Assessment Answers Submitted
                </div>
              ) : (
                <div className={`${m.role === 'user' ? 'rounded-2xl p-4 shadow-sm bg-[var(--accent-color)] text-white' : 'py-2 px-0 text-[var(--ai-msg-text)] bg-transparent'}`}>
                  <div className="whitespace-pre-wrap leading-relaxed">
                    {m.role === 'assistant' 
                      ? renderMessageContent(m.content, (m as any).sources || lastSources) 
                      : m.content}
                  </div>
                </div>
              )}
              {(() => {
                const pdfStep = m.trajectory?.find((t: any) => t.tool === 'create_pdf_summary');
                if (pdfStep && pdfStep.args && pdfStep.args.title) {
                  const safeTitle = pdfStep.args.title.replace(/ /g, '_').toLowerCase().replace(/[^a-z0-9_\-]/g, '') || 'summary';
                  const filename = `${safeTitle}.pdf`;
                  return (
                    <div className="mt-2 flex items-center gap-2 bg-blue-50 p-2.5 rounded-lg border border-blue-200 self-start">
                      <span className="text-sm text-blue-800 font-medium mr-2">PDF Generated</span>
                      <a 
                        href={`http://localhost:8000/api/download/${filename}`}
                        download={filename}
                        target="_blank"
                        rel="noreferrer"
                        className="bg-blue-600 text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-blue-700 transition shadow-sm inline-flex items-center gap-1.5"
                      >
                        <FileText size={14} /> Download {filename}
                      </a>
                    </div>
                  );
                }
                return null;
              })()}
              
              {(() => {
                const riskStep = m.trajectory?.find((t: any) => t.tool === 'analyze_risk_tier');
                if (riskStep && riskStep.args && Array.isArray(riskStep.args.questions) && !handledWebhooks.has(m.id) && session?.messages[session.messages.length - 1].id === m.id) {
                  const questions = riskStep.args.questions;
                  if (questions.length === 0) return null;
                  
                  const wState = wizardState[m.id] || { current: 0, answers: [] };
                  const isComplete = wState.current >= questions.length;

                  if (!isComplete) {
                    return (
                      <div className="mt-2 flex flex-col gap-3 bg-purple-50 p-4 rounded-xl border border-purple-200 self-start w-full max-w-md shadow-sm">
                        <div className="flex items-center justify-between border-b border-purple-100 pb-2">
                          <span className="text-xs font-bold text-purple-700 uppercase tracking-wider flex items-center gap-1.5"><Activity size={14}/> Risk Assessment Wizard</span>
                          <span className="text-xs font-semibold text-purple-400 bg-purple-100 px-2 py-0.5 rounded-full">Step {wState.current + 1} of {questions.length}</span>
                        </div>
                        <p className="text-[15px] text-purple-900 font-medium leading-snug">{questions[wState.current]}</p>
                        <div className="flex flex-col gap-2 mt-2">
                          <div className="flex gap-2">
                            <button 
                              onClick={() => handleWizardAnswer(m.id, questions, questions[wState.current], 'Yes')}
                              className="flex-1 bg-purple-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-purple-700 transition shadow-sm"
                            >
                              Yes
                            </button>
                            <button 
                              onClick={() => handleWizardAnswer(m.id, questions, questions[wState.current], 'No')}
                              className="flex-1 bg-white border border-purple-200 text-purple-700 py-2 rounded-lg text-sm font-semibold hover:bg-purple-50 transition shadow-sm"
                            >
                              No
                            </button>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <input 
                              type="text"
                              value={wizardInput}
                              onChange={(e) => setWizardInput(e.target.value)}
                              placeholder="Or type a custom answer..."
                              className="flex-1 bg-white border border-purple-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-purple-400 placeholder-purple-300"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' && wizardInput.trim()) {
                                  handleWizardAnswer(m.id, questions, questions[wState.current], wizardInput.trim());
                                  setWizardInput('');
                                }
                              }}
                            />
                            <button 
                              onClick={() => {
                                if (wizardInput.trim()) {
                                  handleWizardAnswer(m.id, questions, questions[wState.current], wizardInput.trim());
                                  setWizardInput('');
                                }
                              }}
                              disabled={!wizardInput.trim()}
                              className="bg-purple-100 text-purple-700 px-3 py-1.5 rounded-lg text-sm font-semibold hover:bg-purple-200 transition disabled:opacity-50"
                            >
                              Send
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  }
                }
                return null;
              })()}
              
              {m.role === 'assistant' && m.trajectory?.some((t: any) => t.tool === 'send_message') && webhookStatus[m.id] !== 'hidden' && (!handledWebhooks.has(m.id) || webhookStatus[m.id]) && session?.messages[session.messages.length - 1].id === m.id && (
                <div className="mt-2 flex items-center gap-2 bg-gray-50 p-2.5 rounded-lg border border-gray-200 self-start">
                  {webhookStatus[m.id] === 'sent' ? (
                    <span className="text-sm text-green-600 font-medium px-2">Message sent to Teams!</span>
                  ) : webhookStatus[m.id] === 'error' ? (
                    <span className="text-sm text-red-600 font-medium px-2">Failed to send message.</span>
                  ) : webhookStatus[m.id] === 'sending' ? (
                    <span className="text-sm text-gray-500 font-medium px-2">Sending...</span>
                  ) : (
                    <>
                      <span className="text-sm text-gray-700 font-medium mr-2">Ready to send to Teams?</span>
                      <button 
                        onClick={() => {
                          const step = m.trajectory?.find((t: any) => t.tool === 'send_message');
                          if (step && step.args && step.args.message) {
                            handleConfirmWebhook(m.id, step.args.message);
                          }
                        }}
                        className="bg-blue-600 text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-blue-700 transition shadow-sm"
                      >
                        Yes, send it
                      </button>
                      <button 
                        onClick={() => handleCancelWebhook(m.id)}
                        className="bg-white border border-gray-300 text-gray-700 px-3 py-1.5 rounded-md text-sm font-medium hover:bg-gray-50 transition shadow-sm"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              )}
              
              {m.role === 'assistant' && (m as any).message_id_ref && (
                <button 
                  onClick={() => setTelemetryMessageId((m as any).message_id_ref)} 
                  className="mt-1 self-end text-[11px] font-medium text-[var(--text-primary)] hover:text-[var(--accent-color)] flex items-center gap-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)] px-2.5 py-1 rounded-full shadow-sm transition-all"
                >
                  <Activity size={12}/> View Analytics & Logs
                </button>
              )}
            </div>
          </div>
        ))}
        {isLoadingCurrentSession && (
          <div className="flex justify-start">
            <div className="bg-[var(--bg-tertiary)] rounded-2xl p-4 text-[var(--text-secondary)] font-medium shadow-sm flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-[var(--accent-color)] border-t-transparent rounded-full animate-spin"></div>
              <span className="animate-pulse">{liveStatus}</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} className="h-8" />
            </>
          )}
        </div>
      </div>
      
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 z-20 pointer-events-none">
        <div className="flex relative pointer-events-auto shadow-xl rounded-3xl bg-transparent">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask a question about the EU AI Act..."
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)]/50 backdrop-blur-md text-[var(--text-primary)] placeholder-[var(--text-secondary)] rounded-3xl pl-6 pr-14 py-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)] shadow-sm"
            style={{ backgroundColor: 'color-mix(in srgb, var(--bg-secondary) 85%, transparent)' }}
          />
          {input.trim() && (
            <button 
              onClick={() => handleSend()}
              disabled={isLoadingCurrentSession}
              className="absolute right-2.5 top-2.5 p-2 bg-[var(--accent-color)] text-black rounded-2xl hover:bg-[var(--accent-hover)] transition-colors border-none cursor-pointer shadow-sm flex items-center justify-center"
            >
              <ArrowUp size={18} strokeWidth={3} />
            </button>
          )}
        </div>
      </div>
      
      {telemetryMessageId && (
        <TelemetryModal messageId={telemetryMessageId} onClose={() => setTelemetryMessageId(null)} />
      )}
    </div>
  );
}
