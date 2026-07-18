import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, getAuthToken } from '../config/api';
import { useAuth } from '../context/AuthContext';

const STORAGE_KEY = 'lifelink:ai-chat:sessions';
const ACTIVE_KEY = 'lifelink:ai-chat:active';

const createId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const createSession = (title = 'New chat') => ({
  id: createId(),
  title,
  memoryId: null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  messages: [],
});

const normalizeMessage = (message) => ({
  id: message.id || createId(),
  role: message.role || 'assistant',
  content: message.content || '',
  createdAt: message.createdAt || new Date().toISOString(),
  attachments: message.attachments || [],
  sourceQuery: message.sourceQuery || '',
  confidence: Number.isFinite(message.confidence) ? message.confidence : null,
  webResults: message.webResults || [],
  report: message.report || null,
  charts: message.charts || [],
  references: message.references || [],
  reasoning: message.reasoning || [],
  clarifying: message.clarifying || [],
  orchestration: message.orchestration || null,
  metadata: message.metadata || null,
  followUp: message.followUp || null,
});

const formatTimestamp = (value) => {
  if (!value) return '';
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(value));
  } catch (err) {
    return '';
  }
};

const parseUrl = (value) => {
  if (!value || typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return {
      href: url.href,
      domain: url.hostname.replace(/^www\./, ''),
    };
  } catch (err) {
    return null;
  }
};

const extractUrl = (value) => {
  if (!value || typeof value !== 'string') return null;
  const match = value.match(/https?:\/\/\S+/i);
  return match ? match[0] : null;
};

const BASE_SUGGESTIONS = [
  'Summarize today’s SOS activity.',
  'Show top donor matches near me.',
  'Check hospital capacity risk.',
  'Draft a patient care plan outline.',
  'List key anomalies in the last 24 hours.',
  'Generate a quick incident report.',
];

const AMBULANCE_SUGGESTIONS = [
  'Show the fastest route to the active incident.',
  'Summarize my current assignments and ETAs.',
  'List critical alerts within 5 km of my route.',
  'Create a patient handoff note for the ER team.',
  'Check nearest trauma centers with ICU capacity.',
  'Give me a quick equipment readiness checklist.',
];

const EMERGENCY_SUGGESTIONS = [
  'Summarize the incident severity and patient status.',
  'Suggest the fastest pickup-to-hospital path.',
  'List traffic bottlenecks on the current route.',
  'Draft a quick ER handoff summary.',
  'Show alternate hospitals with lower ETA.',
  'Prepare a one-line radio update for dispatch.',
];

const ASSIGNMENT_SUGGESTIONS = [
  'Prioritize assignments by urgency and ETA.',
  'Highlight any delayed assignments needing reroute.',
  'Summarize active patients and key vitals.',
  'Recommend the next best assignment to accept.',
];

const NAVIGATION_SUGGESTIONS = [
  'Compare fastest vs safest routes for this leg.',
  'Give a turn-by-turn summary for the next 3 km.',
  'Flag any road closures or congestion ahead.',
  'Estimate ETA with current traffic conditions.',
];

const PATIENT_SUGGESTIONS = [
  'Summarize vitals and risk flags for this patient.',
  'Recommend pre-arrival interventions to stabilize.',
  'Generate a concise patient timeline for handoff.',
  'Check if any meds or equipment are missing.',
];

const TRACKING_SUGGESTIONS = [
  'List nearby units with current status.',
  'Identify coverage gaps in the current zone.',
  'Summarize unit ETAs for the next 15 minutes.',
  'Flag any units that have stopped reporting.',
];

const HISTORY_SUGGESTIONS = [
  'Summarize today’s completed missions.',
  'Highlight longest response times and causes.',
  'Generate a brief performance recap for the shift.',
];

const getQuickSuggestions = (moduleKey) => {
  const key = (moduleKey || '').toLowerCase();
  if (key.includes('emergency')) return EMERGENCY_SUGGESTIONS;
  if (key.includes('assignments')) return ASSIGNMENT_SUGGESTIONS;
  if (key.includes('navigation') || key.includes('route')) return NAVIGATION_SUGGESTIONS;
  if (key.includes('patient')) return PATIENT_SUGGESTIONS;
  if (key.includes('live-tracking') || key.includes('tracking')) return TRACKING_SUGGESTIONS;
  if (key.includes('history')) return HISTORY_SUGGESTIONS;
  if (key.includes('ambulance') || key.includes('emergency') || key.includes('response')) {
    return AMBULANCE_SUGGESTIONS;
  }
  return BASE_SUGGESTIONS;
};

const LifelinkAiChat = ({ variant = 'panel', onClose, location, moduleKey = 'general' }) => {
  const { user, loading: authLoading } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [isRemote, setIsRemote] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [suggestionsVisible, setSuggestionsVisible] = useState(true);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('chat');
  const [webSearch, setWebSearch] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [attachmentError, setAttachmentError] = useState('');
  const scrollRef = useRef(null);
  const isAgentMode = mode === 'agent';
  const quickSuggestions = useMemo(() => getQuickSuggestions(moduleKey), [moduleKey]);

  useEffect(() => {
    if (authLoading) return;
    setIsRemote(Boolean(getAuthToken()));
  }, [authLoading, user]);

  const initLocalSessions = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      const parsed = stored ? JSON.parse(stored) : [];
      const initial = parsed.length ? parsed : [createSession()];
      const storedActive = localStorage.getItem(ACTIVE_KEY);
      setSessions(initial);
      setActiveId(storedActive && initial.some((session) => session.id === storedActive)
        ? storedActive
        : initial[0].id);
    } catch (err) {
      const fallback = [createSession()];
      setSessions(fallback);
      setActiveId(fallback[0].id);
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (isRemote) {
      const loadRemote = async () => {
        setLoadingHistory(true);
        const res = await apiFetch('/v2/agents/chat/sessions', { cache: false });
        if (res.status === 401) {
          setIsRemote(false);
          initLocalSessions();
          setLoadingHistory(false);
          return;
        }
        if (res.ok) {
          const list = (res.data?.sessions || []).map((item) => ({
            id: item.id,
            title: item.title,
            memoryId: item.id,
            createdAt: item.createdAt,
            updatedAt: item.updatedAt,
            messages: [],
            messageCount: item.messageCount || 0,
            module: item.module,
            mode: item.mode,
          }));
          const stored = localStorage.getItem(STORAGE_KEY);
          const parsed = stored ? JSON.parse(stored) : [];
          const localHasMessages = parsed.some((session) => (session.messages || []).length > 0);
          const remoteHasMessages = list.some((session) => (session.messageCount || 0) > 0);
          if (!remoteHasMessages && localHasMessages) {
            setIsRemote(false);
            setSessions(parsed);
            setActiveId(parsed[0]?.id || null);
            setLoadingHistory(false);
            return;
          }
          if (list.length === 0) {
            if (parsed.length > 0) {
              setIsRemote(false);
              setSessions(parsed);
              setActiveId(parsed[0].id);
              setLoadingHistory(false);
              return;
            }
            const created = await apiFetch('/v2/agents/chat/sessions', {
              method: 'POST',
              body: JSON.stringify({ module: moduleKey, mode }),
            });
            if (created.status === 401) {
              setIsRemote(false);
              initLocalSessions();
            } else if (created.ok && created.data?.session) {
              const session = created.data.session;
              setSessions([
                {
                  id: session.id,
                  title: session.title,
                  memoryId: session.id,
                  createdAt: session.createdAt,
                  updatedAt: session.updatedAt,
                  messages: [],
                  module: session.module,
                  mode: session.mode,
                },
              ]);
              setActiveId(session.id);
            }
          } else {
            setSessions(list);
            setActiveId(list[0].id);
          }
        }
        setLoadingHistory(false);
      };
      loadRemote();
      return;
    }
    initLocalSessions();
  }, [isRemote]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    if (activeId) {
      localStorage.setItem(ACTIVE_KEY, activeId);
    }
  }, [sessions, activeId]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeId),
    [sessions, activeId]
  );

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [activeSession?.messages?.length, loading]);

  useEffect(() => {
    if (activeSession?.messages?.length) {
      setSuggestionsVisible(false);
    }
  }, [activeSession?.messages?.length]);

  useEffect(() => {
    if (!isRemote || !activeId) return;
    const loadMessages = async () => {
      setLoadingHistory(true);
      const res = await apiFetch(`/v2/agents/chat/sessions/${activeId}`, { cache: false });
      if (res.ok && res.data?.session) {
        const sessionData = res.data.session;
        setSessions((prev) => prev.map((item) => (
          item.id === activeId
            ? { ...item, title: sessionData.title, updatedAt: sessionData.updatedAt, messages: sessionData.messages || [] }
            : item
        )));
      }
      setLoadingHistory(false);
    };
    loadMessages();
  }, [activeId, isRemote]);

  const updateSession = (sessionId, updater) => {
    setSessions((prev) => prev.map((session) => (
      session.id === sessionId ? updater(session) : session
    )));
  };

  const handleNewChat = () => {
    if (isRemote) {
      const createRemote = async () => {
        setLoadingHistory(true);
        const res = await apiFetch('/v2/agents/chat/sessions', {
          method: 'POST',
          body: JSON.stringify({ module: moduleKey, mode }),
        });
        if (res.status === 401) {
          setIsRemote(false);
          initLocalSessions();
          setLoadingHistory(false);
          return;
        }
        if (res.ok && res.data?.session) {
          const session = res.data.session;
          setSessions((prev) => [
            {
              id: session.id,
              title: session.title,
              memoryId: session.id,
              createdAt: session.createdAt,
              updatedAt: session.updatedAt,
              messages: [],
              module: session.module,
              mode: session.mode,
            },
            ...prev,
          ]);
          setActiveId(session.id);
        }
        setLoadingHistory(false);
      };
      createRemote();
    } else {
      const next = createSession();
      setSessions((prev) => [next, ...prev]);
      setActiveId(next.id);
    }
    setShowHistory(false);
    setInput('');
    setAttachments([]);
    setAttachmentError('');
    setError('');
    setSuggestionsVisible(true);
  };

  const handleSelectSession = (sessionId) => {
    setActiveId(sessionId);
    setShowHistory(false);
  };

  const handleFileChange = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setAttachmentError('');

    const next = [];
    for (const file of files) {
      let text = '';
      try {
        if (file.type.startsWith('text/') || /\.(txt|md|csv|json)$/i.test(file.name)) {
          text = await file.text();
        }
      } catch (err) {
        text = '';
      }
      if (text.length > 4000) {
        text = `${text.slice(0, 4000)}...`;
      }
      next.push({
        id: createId(),
        name: file.name,
        type: file.type || 'application/octet-stream',
        size: file.size || 0,
        text,
      });
    }

    setAttachments((prev) => prev.concat(next));
    event.target.value = '';
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => prev.filter((item) => item.id !== id));
  };

  const handleSend = async (overrideText) => {
    const trimmed = (overrideText ?? input).trim();
    if (!trimmed && attachments.length === 0) return;

    let sessionForSend = activeSession;
    if (!sessionForSend) {
      const next = createSession();
      setSessions((prev) => [next, ...prev]);
      setActiveId(next.id);
      sessionForSend = next;
    }

    if (suggestionsVisible) {
      setSuggestionsVisible(false);
    }

    const userMessage = normalizeMessage({
      role: 'user',
      content: trimmed || 'Analyze the attached files.',
      attachments,
    });

    setSessions((prev) => {
      const exists = prev.some((session) => session.id === sessionForSend.id);
      const updater = (session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        title: session.messages.length === 0 ? userMessage.content.slice(0, 32) : session.title,
        messages: [...session.messages, userMessage],
      });
      if (!exists) {
        return [updater(sessionForSend), ...prev];
      }
      return prev.map((session) => (
        session.id === sessionForSend.id ? updater(session) : session
      ));
    });

    setInput('');
    setAttachments([]);
    setError('');
    setLoading(true);

    try {
      const payload = {
        query: trimmed || 'Analyze the attached files and provide insights.',
        memoryId: sessionForSend.memoryId || sessionForSend.id,
        supervised: isAgentMode,
        mode,
        module: moduleKey,
        web_search: webSearch,
        attachments: userMessage.attachments.map((item) => ({
          name: item.name,
          type: item.type,
          size: item.size,
          text: item.text,
        })),
      };
      if (location?.lat && location?.lng) {
        payload.latitude = location.lat;
        payload.longitude = location.lng;
      }

      const res = await apiFetch('/v2/agents/ask', {
        method: 'POST',
        body: JSON.stringify(payload),
        timeoutMs: 35000,
      });

      if (!res.ok) {
        throw new Error(res.data?.detail || res.data?.error || 'AI response failed');
      }

      const data = res.data || {};
      const assistantMessage = normalizeMessage({
        role: 'assistant',
        content: data.answer || 'No response generated.',
        sourceQuery: payload.query,
        confidence: data.confidence,
        webResults: data.web_results || [],
        report: data.report,
        charts: data.charts,
        references: data.references,
        reasoning: data.reasoning,
        clarifying: data.clarifying_questions || [],
        orchestration: data.orchestration,
        metadata: data.metadata,
      });

      const nextMemoryId = data.memoryId || sessionForSend.memoryId || sessionForSend.id;
      setSessions((prev) => prev.map((session) => (
        session.id === sessionForSend.id
          ? {
            ...session,
            id: nextMemoryId,
            memoryId: nextMemoryId,
            updatedAt: new Date().toISOString(),
            messages: [...session.messages, assistantMessage],
          }
          : session
      )));
      if (nextMemoryId !== sessionForSend.id) {
        setActiveId(nextMemoryId);
      }
      if (isRemote && data.session) {
        setSessions((prev) => prev.map((item) => (
          item.id === data.session.id
            ? {
              ...item,
              title: data.session.title || item.title,
              updatedAt: data.session.updatedAt || item.updatedAt,
              module: data.session.module || item.module,
              mode: data.session.mode || item.mode,
            }
            : item
        )));
      }
    } catch (err) {
      setError(err.message || 'AI request failed.');
      updateSession(sessionForSend.id, (session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        messages: [...session.messages, normalizeMessage({ role: 'assistant', content: 'AI response failed. Please retry.' })],
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async (message) => {
    if (!activeSession || loading) return;
    const lastUser = [...(activeSession.messages || [])].reverse().find((item) => item.role === 'user');
    const query = message?.sourceQuery || lastUser?.content || '';
    if (!query) return;
    const attachmentsForRegen = lastUser?.attachments || [];

    if (activeSession.messages?.length > 0 && activeSession.messages[activeSession.messages.length - 1].role === 'assistant') {
      setSessions((prev) => prev.map((session) => (
        session.id === activeSession.id
          ? { ...session, messages: session.messages.slice(0, -1), updatedAt: new Date().toISOString() }
          : session
      )));
    }

    setLoading(true);
    setError('');
    try {
      const payload = {
        query,
        memoryId: activeSession.memoryId || activeSession.id,
        supervised: isAgentMode,
        mode,
        module: moduleKey,
        web_search: webSearch,
        regenerate: true,
        attachments: attachmentsForRegen.map((item) => ({
          name: item.name,
          type: item.type,
          size: item.size,
          text: item.text,
        })),
      };
      if (location?.lat && location?.lng) {
        payload.latitude = location.lat;
        payload.longitude = location.lng;
      }

      const res = await apiFetch('/v2/agents/ask', {
        method: 'POST',
        body: JSON.stringify(payload),
        timeoutMs: 35000,
      });

      if (!res.ok) {
        throw new Error(res.data?.detail || res.data?.error || 'AI response failed');
      }

      const data = res.data || {};
      const assistantMessage = normalizeMessage({
        role: 'assistant',
        content: data.answer || 'No response generated.',
        sourceQuery: payload.query,
        confidence: data.confidence,
        webResults: data.web_results || [],
        report: data.report,
        charts: data.charts,
        references: data.references,
        reasoning: data.reasoning,
        clarifying: data.clarifying_questions || [],
        orchestration: data.orchestration,
        metadata: data.metadata,
      });

      updateSession(activeSession.id, (session) => ({
        ...session,
        memoryId: data.memoryId || session.memoryId,
        updatedAt: new Date().toISOString(),
        messages: [...session.messages, assistantMessage],
      }));
      const nextMemoryId = data.memoryId || activeSession.memoryId || activeSession.id;
      if (nextMemoryId !== activeSession.id) {
        setSessions((prev) => prev.map((item) => (
          item.id === activeSession.id
            ? { ...item, id: nextMemoryId, memoryId: nextMemoryId }
            : item
        )));
        setActiveId(nextMemoryId);
      }
      if (isRemote && data.session) {
        setSessions((prev) => prev.map((item) => (
          item.id === data.session.id
            ? {
              ...item,
              title: data.session.title || item.title,
              updatedAt: data.session.updatedAt || item.updatedAt,
              module: data.session.module || item.module,
              mode: data.session.mode || item.mode,
            }
            : item
        )));
      }
    } catch (err) {
      setError(err.message || 'AI request failed.');
    } finally {
      setLoading(false);
    }
  };

  const containerClass = variant === 'panel'
    ? 'flex h-full flex-col rounded-2xl bg-slate-50'
    : 'flex flex-col min-h-[70vh] bg-slate-50';

  return (
    <div className={containerClass}>
      <div className="flex items-center justify-between border-b border-slate-200 px-3 pb-2 pt-2">
        <button
          type="button"
          onClick={() => setShowHistory((prev) => !prev)}
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[11px] font-semibold ${showHistory ? 'border-sky-600 bg-sky-600 text-white' : 'border-sky-200 bg-sky-50 text-sky-700'}`}
        >
          <i className="fas fa-clock-rotate-left"></i>
          History
        </button>
        <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-slate-700">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white text-[12px] shadow">
            <i className="fas fa-heartbeat"></i>
          </span>
          <span>LifeLink AI</span>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-semibold ${isRemote ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600 border border-slate-200'}`}
        >
          {isRemote ? 'Signed in' : 'Guest'}
        </span>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <div ref={scrollRef} className="mt-3 flex-[3] min-h-0 overflow-y-auto overflow-x-hidden px-3 sm:px-4 pb-3">
          {showHistory ? (
            <div className="space-y-4">
              <button
                type="button"
                onClick={handleNewChat}
                className="w-full rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-left text-[12px] font-semibold text-sky-700"
              >
                <i className="fas fa-plus mr-2"></i>
                New chat
              </button>
              <div className="space-y-3">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => handleSelectSession(session.id)}
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${session.id === activeId ? 'border-sky-600 bg-sky-600 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'}`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className={`text-[12px] font-semibold ${session.id === activeId ? 'text-white' : 'text-slate-900'}`}>
                          {session.title || 'New chat'}
                        </p>
                        <p className={`text-[10px] ${session.id === activeId ? 'text-sky-100' : 'text-slate-500'}`}>
                          Updated {formatTimestamp(session.updatedAt || session.createdAt)}
                        </p>
                      </div>
                      <span className={`text-[10px] ${session.id === activeId ? 'text-sky-100' : 'text-slate-400'}`}>
                        {session.messageCount ?? session.messages.length} msgs
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {suggestionsVisible && (activeSession?.messages || []).length === 0 && (
                <div className="mb-4 grid gap-2">
                  {quickSuggestions.slice(0, 4).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => handleSend(item)}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-[12px] text-slate-600 hover:border-slate-300"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              )}
              {(activeSession?.messages || []).map((message) => (
                <div key={message.id} className="w-full flex justify-center mb-4">
                  <div className={`w-full max-w-2xl flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`rounded-2xl px-3 py-2 text-[13px] leading-5 shadow-sm break-words overflow-hidden ${message.role === 'user' ? 'bg-sky-600 text-white' : 'bg-white text-slate-800 border border-slate-200'}`}>
                      <p className="whitespace-pre-wrap break-words">{message.content}</p>

                      {message.followUp && (
                        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                          {message.followUp}
                        </div>
                      )}

                      {message.clarifying?.length > 0 && (
                        <div className="mt-3 space-y-1 text-[11px] text-slate-500">
                          <p className="font-semibold text-slate-700 text-[11px]">Clarify:</p>
                          {message.clarifying.map((item) => (
                            <p key={item}>• {item}</p>
                          ))}
                        </div>
                      )}

                      {message.report && (
                        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-600">
                          <p className="font-semibold text-slate-800 text-[11px]">{message.report.title || 'AI Report'}</p>
                          <p className="mt-1">{message.report.summary}</p>
                          {Array.isArray(message.report.highlights) && (
                            <ul className="mt-2 space-y-1">
                              {message.report.highlights.map((item) => (
                                <li key={item}>• {item}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}

                      {Array.isArray(message.charts) && message.charts.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {message.charts.map((chart, index) => (
                            <MiniBarChart key={`${chart.title}-${index}`} title={chart.title} data={chart.data || []} />
                          ))}
                        </div>
                      )}

                      {message.orchestration?.actions?.length > 0 && (
                        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-800">
                          <p className="font-semibold text-[11px]">Proposed actions (needs approval)</p>
                          <ul className="mt-2 space-y-1">
                            {message.orchestration.actions.map((action, index) => (
                              <li key={`${action.type || 'action'}-${index}`}>• {action.type || 'Action'}: {action.summary || action.status || 'Queued'}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {message.reasoning?.length > 0 && (
                        <div className="mt-3 text-[11px] text-slate-500">
                          <p className="font-semibold text-slate-700 text-[11px]">Reasoning</p>
                          {message.reasoning.map((item) => (
                            <p key={item}>• {item}</p>
                          ))}
                        </div>
                      )}

                      {message.references?.length > 0 && (
                        <div className="mt-3 text-[11px] text-slate-500">
                          <p className="font-semibold text-slate-700 text-[11px]">References</p>
                          <div className="mt-2 grid gap-2">
                            {message.references.map((ref, index) => {
                              const refUrl = ref?.url || extractUrl(ref?.detail || '');
                              const parsed = parseUrl(refUrl);
                              return (
                                <div
                                  key={`${ref.title || 'ref'}-${index}`}
                                  className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2"
                                >
                                  {parsed ? (
                                    <a
                                      href={parsed.href}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="block"
                                    >
                                      <p className="text-[12px] font-semibold text-amber-900">{ref.title || parsed.domain}</p>
                                      <p className="text-[10px] text-amber-700">{parsed.domain}</p>
                                    </a>
                                  ) : (
                                    <>
                                      <p className="text-[12px] font-semibold text-amber-900">{ref.title || 'Reference'}</p>
                                      <p className="text-[10px] text-amber-700 break-words">{ref.detail}</p>
                                    </>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      {message.webResults?.length > 0 && (
                        <div className="mt-3 text-[11px] text-slate-500">
                          <p className="font-semibold text-slate-700 text-[11px]">Web results</p>
                          <div className="mt-2 grid gap-2">
                            {message.webResults.map((item) => {
                              const parsed = parseUrl(item.url);
                              const linkText = item.title?.trim() || parsed?.domain || 'Source';
                              const linkSubtext = parsed?.domain || item.url;
                              return (
                                <a
                                  key={`${item.url}-${linkText}`}
                                  href={parsed?.href || item.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block rounded-xl border border-sky-100 bg-sky-50 px-3 py-2"
                                >
                                  <p className="text-[12px] font-semibold text-sky-900">{linkText}</p>
                                  <p className="text-[10px] text-sky-700 break-words">{linkSubtext}</p>
                                </a>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      {message.role === 'assistant' && (
                        <div className="mt-3 flex items-center gap-3 text-[10px] text-slate-500">
                          <button
                            type="button"
                            onClick={() => handleRegenerate(message)}
                            className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-700"
                          >
                            <i className="fas fa-rotate-right"></i>
                            Regenerate
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="w-full flex justify-center">
                  <div className="w-full max-w-2xl">
                    <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3 text-[12px] text-slate-500">Thinking...</div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!showHistory && (
          <div className="flex-[1] h-[25%] max-h-[220px] min-h-[140px] border-t border-slate-200 bg-white/95 backdrop-blur px-3 sm:px-4 py-3 sticky bottom-0 sm:static">
            {error && <p className="mb-1 text-[10px] text-rose-600">{error}</p>}
            {attachments.length > 0 && (
              <div className="mb-1 flex flex-wrap gap-2">
                {attachments.map((item) => (
                  <span key={item.id} className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[10px] text-slate-600">
                    {item.name}
                    <button type="button" onClick={() => removeAttachment(item.id)} className="text-slate-400">x</button>
                  </span>
                ))}
              </div>
            )}
            {attachmentError && <p className="text-[10px] text-rose-600">{attachmentError}</p>}
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="inline-flex items-center rounded-full border border-slate-200 bg-white p-1 text-[10px]">
                <button
                  type="button"
                  onClick={() => setMode('chat')}
                  className={`px-3 py-1 rounded-full ${mode === 'chat' ? 'bg-sky-600 text-white' : 'text-slate-500'}`}
                >
                  Chat mode
                </button>
                <button
                  type="button"
                  onClick={() => setMode('agent')}
                  className={`px-3 py-1 rounded-full ${mode === 'agent' ? 'bg-indigo-600 text-white' : 'text-slate-500'}`}
                >
                  Agent mode
                </button>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <button
                  type="button"
                  onClick={() => setWebSearch((prev) => !prev)}
                  className={`px-2 py-1 rounded-full border ${webSearch ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-white text-slate-500'}`}
                >
                  <i className="fas fa-globe"></i> Web {webSearch ? 'on' : 'off'}
                </button>
                <span>Module: {moduleKey}</span>
                <label className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-600 cursor-pointer">
                  <i className="fas fa-paperclip"></i>
                  <input
                    type="file"
                    multiple
                    accept=".txt,.md,.csv,.json,application/pdf,image/*,video/*"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                </label>
              </div>
            </div>
            <p className="mb-1 text-[10px] text-slate-500">
              {isAgentMode ? 'Agent mode proposes actions and awaits your approval.' : 'Chat mode answers questions and summarizes insights.'}
            </p>
            <div className="relative">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    handleSend();
                  }
                }}
                rows={variant === 'panel' ? 2 : 3}
                placeholder="Ask LifeLink AI..."
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-3 pr-12 text-[13px] leading-5 shadow-sm min-h-[80px]"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={loading}
                aria-label="Send message"
                className="absolute bottom-2 right-2 z-20 inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white shadow-lg shadow-sky-500/20"
              >
                <i className={`fas ${loading ? 'fa-spinner fa-spin' : 'fa-arrow-up'}`}></i>
              </button>
            </div>
            <div className="mt-1 text-[10px] text-slate-400">
              Press Enter to send, Shift + Enter for a new line.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LifelinkAiChat;