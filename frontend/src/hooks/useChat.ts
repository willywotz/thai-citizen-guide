import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage, AgentStep, StreamingState } from '@/types';
import type {
  StepEvent, AgenciesEvent, IntentEvent, RoutingEvent,
  AgencyStartEvent, AgencyRespondedEvent, AgencyVerifiedEvent,
  AnswerEvent, DoneEvent, ErrorEvent,
} from '@/types/chat';
import { sendChatQuery, sendChatQuerySSE } from '@/services/chatApi';
import { updateMessageRating } from '@/services/feedbackApi';
import { mockAgentSteps } from '@/data/mockData';
import { generateUniqueId } from '@/lib/utils';

const INITIAL_STREAMING_STATE: StreamingState = {
  pipelineSteps: [],
  currentStep: null,
  agencies: [],
  intent: null,
  routing: null,
  agencyStatuses: {},
  answer: null,
  sections: [],
  errors: [],
  sessionId: null,
  totalMs: null,
  done: false,
};

const STEP_LABELS: Record<string, { icon: string; label: string }> = {
  discover: { icon: '🔍', label: 'ค้นหาหน่วยงาน' },
  classify: { icon: '🧠', label: 'วิเคราะห์คำถาม' },
  invoke: { icon: '🔗', label: 'สืบค้นจากหน่วยงาน' },
  verify: { icon: '✅', label: 'ตรวจสอบความเกี่ยวข้อง' },
  synthesize: { icon: '📝', label: 'สังเคราะห์คำตอบ' },
};

function buildAgentStepsFromStreaming(state: StreamingState): AgentStep[] {
  const steps: AgentStep[] = [];

  for (const ps of state.pipelineSteps) {
    const info = STEP_LABELS[ps.name] ?? { icon: '⚙️', label: ps.name };
    steps.push({
      icon: info.icon,
      label: info.label + (ps.ms ? ` (${(ps.ms / 1000).toFixed(1)}s)` : ''),
      status: ps.status === 'done' ? 'done' : 'active',
    });
  }

  const agencyEntries = Object.values(state.agencyStatuses);
  if (agencyEntries.length > 0) {
    for (const a of agencyEntries) {
      const statusIcon = a.status === 'error' ? '❌' : a.status === 'passed' ? '✅' : a.status === 'rejected' ? '⚠️' : a.status === 'ok' ? '⏳' : '🔗';
      steps.push({
        icon: statusIcon,
        label: a.agencyName ?? a.agencyId,
        detail: a.errorType ?? undefined,
        status: a.status === 'running' ? 'active' : 'done',
      });
    }
  }

  return steps;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeStepCount, setActiveStepCount] = useState(0);
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>(mockAgentSteps);
  const [streamingState, setStreamingState] = useState<StreamingState>(INITIAL_STREAMING_STATE);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Ref to always have latest streaming state in closures
  const streamingRef = useRef<StreamingState>(INITIAL_STREAMING_STATE);

  // Keep ref in sync
  useEffect(() => {
    streamingRef.current = streamingState;
  }, [streamingState]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeStepCount, streamingState.currentStep]);

  const handleRate = useCallback((id: string, rating: 'up' | 'down', feedbackText?: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, rating } : m)));
    updateMessageRating(id, rating, feedbackText);
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsTyping(false);
    setActiveStepCount(0);
    setStreamingState(INITIAL_STREAMING_STATE);
    streamingRef.current = INITIAL_STREAMING_STATE;
  }, []);

  const finalizeStreaming = useCallback(() => {
    const state = streamingRef.current;
    if (state.answer) {
      const aiMsg: ChatMessage = {
        id: generateUniqueId(),
        role: 'assistant',
        content: state.answer,
        timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
        agentSteps: buildAgentStepsFromStreaming(state),
        sources: state.sections.flatMap((s) =>
          s.agencies.map((a) => ({ agency: a.name, url: '', title: s.title }))
        ),
        rating: null,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } else if (!state.done) {
      // Stream ended without answer or done — connection lost
      setMessages((prev) => [
        ...prev,
        {
          id: generateUniqueId(),
          role: 'assistant',
          content: 'ขออภัย การเชื่อมต่อถูกตัด โปรดลองอีกครั้ง',
          timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
          rating: null,
        },
      ]);
    }
    if (state.sessionId) {
      setConversationId(state.sessionId);
    }
    setIsTyping(false);
    setActiveStepCount(0);
  }, []);

  const handleSend = useCallback(async (text?: string) => {
    const question = text || input.trim();
    if (!question || isTyping) return;

    const userMsg: ChatMessage = {
      id: generateUniqueId(),
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);
    setActiveStepCount(0);
    const freshState = { ...INITIAL_STREAMING_STATE };
    setStreamingState(freshState);
    streamingRef.current = freshState;

    const abortController = new AbortController();
    abortRef.current = abortController;

    // Callbacks update state via setStreamingState + streamingRef
    const onStep = (event: StepEvent) => {
      setStreamingState((prev) => {
        const steps = [...prev.pipelineSteps];
        const existingIdx = steps.findIndex((s) => s.name === event.name && s.status === 'running');
        if (event.status === 'running') {
          steps.push({ name: event.name, status: 'running', ms: null });
        } else if (existingIdx >= 0) {
          steps[existingIdx] = { name: event.name, status: 'done', ms: event.ms };
        } else {
          steps.push({ name: event.name, status: 'done', ms: event.ms });
        }
        const next = { ...prev, pipelineSteps: steps, currentStep: event.status === 'running' ? event.name : prev.currentStep };
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencies = (event: AgenciesEvent) => {
      setStreamingState((prev) => {
        const next = { ...prev, agencies: event.agencies };
        streamingRef.current = next;
        return next;
      });
    };

    const onIntent = (event: IntentEvent) => {
      setStreamingState((prev) => {
        const next = { ...prev, intent: event };
        streamingRef.current = next;
        return next;
      });
    };

    const onRouting = (event: RoutingEvent) => {
      setStreamingState((prev) => {
        const next = { ...prev, routing: event };
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyStart = (event: AgencyStartEvent) => {
      setStreamingState((prev) => {
        const statuses = { ...prev.agencyStatuses };
        statuses[event.agency_id] = {
          agencyId: event.agency_id,
          agencyName: event.agency_name,
          query: event.query,
          sectionLabel: event.section_label,
          status: 'running',
        };
        const next = { ...prev, agencyStatuses: statuses };
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyResponded = (event: AgencyRespondedEvent) => {
      setStreamingState((prev) => {
        const statuses = { ...prev.agencyStatuses };
        const existing = statuses[event.agency_id] || {
          agencyId: event.agency_id,
          agencyName: event.agency_name,
          query: '',
          sectionLabel: event.section_label,
          status: 'pending' as const,
        };
        statuses[event.agency_id] = {
          ...existing,
          status: event.status === 'ok' ? 'ok' : 'error',
          errorType: event.error_type,
        };
        const next = { ...prev, agencyStatuses: statuses };
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyVerified = (event: AgencyVerifiedEvent) => {
      setStreamingState((prev) => {
        const statuses = { ...prev.agencyStatuses };
        const existing = statuses[event.agency_id];
        if (existing) {
          statuses[event.agency_id] = {
            ...existing,
            status: event.status,
            relevanceScore: event.relevance_score,
          };
        }
        const next = { ...prev, agencyStatuses: statuses };
        streamingRef.current = next;
        return next;
      });
    };

    const onAnswer = (event: AnswerEvent) => {
      setStreamingState((prev) => {
        const next = { ...prev, answer: event.answer, sections: event.sections, errors: event.errors };
        streamingRef.current = next;
        return next;
      });
    };

    const onDone = (_event: DoneEvent) => {
      setStreamingState((prev) => {
        const next = { ...prev, sessionId: _event.session_id, totalMs: _event.total_ms, done: true };
        streamingRef.current = next;
        return next;
      });
    };

    const onError = (event: ErrorEvent) => {
      setStreamingState((prev) => {
        const next = {
          ...prev,
          errors: [...prev.errors, { agency: '', name: '', errorType: 'SSE', message: event.message }],
          done: true,
        };
        streamingRef.current = next;
        return next;
      });
    };

    try {
      // Try SSE first
      const usedSSE = await sendChatQuerySSE(
        { query: question, conversation_id: conversationId || undefined },
        { onStep, onAgencies, onIntent, onRouting, onAgencyStart, onAgencyResponded, onAgencyVerified, onAnswer, onDone, onError },
        abortController.signal,
      );

      if (abortController.signal.aborted) return;

      if (usedSSE) {
        finalizeStreaming();
        return;
      }

      // Fallback: regular JSON POST
      const response = await sendChatQuery({ query: question, conversation_id: conversationId || undefined });

      if (response.success) {
        setConversationId(response.conversation_id);
        setCurrentSteps(response.data.agentSteps as AgentStep[]);
        setActiveStepCount(response.data.agentSteps.length);

        const aiMsgId = response.data.message_id || generateUniqueId();
        const aiMsg: ChatMessage = {
          id: aiMsgId,
          role: 'assistant',
          content: response.data.answer,
          timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
          agentSteps: response.data.agentSteps as AgentStep[],
          sources: response.data.references.map((ref) => ({
            agency: ref.agency,
            url: ref.url,
            title: ref.title,
          })),
          rating: null,
        };
        setMessages((prev) => [...prev, aiMsg]);
        setIsTyping(false);
        setActiveStepCount(0);
        return;
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;

      setCurrentSteps([]);
      setActiveStepCount(0);
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: generateUniqueId(),
          role: 'assistant',
          content: 'ขออภัย ฉันไม่สามารถตอบคำถามได้ในขณะนี้ โปรดลองอีกครั้งในภายหลัง',
          timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
          rating: null,
        },
      ]);
    }
  }, [input, isTyping, conversationId, finalizeStreaming]);

  const reset = useCallback(() => {
    setMessages([]);
    setIsTyping(false);
    setActiveStepCount(0);
    setInput('');
    setCurrentSteps(mockAgentSteps);
    setConversationId(null);
    setStreamingState(INITIAL_STREAMING_STATE);
    streamingRef.current = INITIAL_STREAMING_STATE;
    abortRef.current?.abort();
  }, []);

  return {
    messages,
    input,
    setInput,
    isTyping,
    activeStepCount,
    currentSteps,
    streamingState,
    scrollRef,
    handleSend,
    handleRate,
    reset,
    cancelStream,
    hasMessages: messages.length > 0,
  };
}