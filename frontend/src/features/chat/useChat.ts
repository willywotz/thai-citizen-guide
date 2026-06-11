import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage, AgentStep, StreamingState } from '@/shared/types';
import { sendChatQuery, sendChatQuerySSE } from '@/features/chat/chatApi';
import { updateMessageRating } from '@/features/chat/feedbackApi';
import { mockAgentSteps } from '@/shared/data/mockData';
import { generateUniqueId } from '@/shared/lib/utils';
import {
  INITIAL_STREAMING_STATE,
  applyStepEvent,
  applyAgenciesEvent,
  applyIntentEvent,
  applyRoutingEvent,
  applyAgencyStartEvent,
  applyAgencyRespondedEvent,
  applyAgencyVerifiedEvent,
  applyAnswerEvent,
  applyDoneEvent,
  applyErrorEvent,
  buildAiMessageFromState,
  buildConnectionLostMessage,
  buildGenericErrorMessage,
  formatTimestamp,
} from './chatHelpers';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeStepCount, setActiveStepCount] = useState(0);
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>(mockAgentSteps);
  const [streamingState, setStreamingState] = useState<StreamingState>(INITIAL_STREAMING_STATE);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  // B2: ref always holds the latest conversationId to avoid stale closure in handleSend
  const conversationIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Ref to always have latest streaming state in closures
  const streamingRef = useRef<StreamingState>(INITIAL_STREAMING_STATE);

  // Keep ref in sync
  useEffect(() => {
    streamingRef.current = streamingState;

    if (streamingState.sessionId) {
      setConversationId(streamingState.sessionId);
      conversationIdRef.current = streamingState.sessionId;
    }
  }, [streamingState]);

  // B2: safety-net sync for direct setConversationId calls
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // B7: abort in-flight SSE on unmount to prevent state updates after unmount
  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeStepCount, streamingState.currentStep]);

  // B6: optimistic update with rollback on API failure
  const handleRate = useCallback(async (id: string, rating: 'up' | 'down', feedbackText?: string) => {
    let previousRating: 'up' | 'down' | null | undefined;
    setMessages((prev) => {
      const msg = prev.find((m) => m.id === id);
      previousRating = msg?.rating;
      return prev.map((m) => (m.id === id ? { ...m, rating } : m));
    });
    const ok = await updateMessageRating(id, rating, feedbackText);
    if (!ok) {
      // Roll back to previous rating
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, rating: previousRating ?? null } : m))
      );
    }
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
    const aiMsg = buildAiMessageFromState(state);
    if (aiMsg) {
      setMessages((prev) => [...prev, aiMsg]);
    } else if (state.done && state.errors.length > 0) {
      // B8/S1: SSE error event set done=true with no answer — surface an error bubble
      setMessages((prev) => [...prev, buildGenericErrorMessage()]);
    } else if (!state.done) {
      // Stream ended without answer or done — connection lost
      setMessages((prev) => [...prev, buildConnectionLostMessage()]);
    }
    if (state.sessionId) {
      setConversationId(state.sessionId);
      conversationIdRef.current = state.sessionId;
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
      timestamp: formatTimestamp(),
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
    const onStep: Parameters<typeof sendChatQuerySSE>[1]['onStep'] = (event) => {
      setStreamingState((prev) => {
        const next = applyStepEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencies: Parameters<typeof sendChatQuerySSE>[1]['onAgencies'] = (event) => {
      setStreamingState((prev) => {
        const next = applyAgenciesEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onIntent: Parameters<typeof sendChatQuerySSE>[1]['onIntent'] = (event) => {
      setStreamingState((prev) => {
        const next = applyIntentEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onRouting: Parameters<typeof sendChatQuerySSE>[1]['onRouting'] = (event) => {
      setStreamingState((prev) => {
        const next = applyRoutingEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyStart: Parameters<typeof sendChatQuerySSE>[1]['onAgencyStart'] = (event) => {
      setStreamingState((prev) => {
        const next = applyAgencyStartEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyResponded: Parameters<typeof sendChatQuerySSE>[1]['onAgencyResponded'] = (event) => {
      setStreamingState((prev) => {
        const next = applyAgencyRespondedEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onAgencyVerified: Parameters<typeof sendChatQuerySSE>[1]['onAgencyVerified'] = (event) => {
      setStreamingState((prev) => {
        const next = applyAgencyVerifiedEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onAnswer: Parameters<typeof sendChatQuerySSE>[1]['onAnswer'] = (event) => {
      setStreamingState((prev) => {
        const next = applyAnswerEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onDone: Parameters<typeof sendChatQuerySSE>[1]['onDone'] = (event) => {
      setStreamingState((prev) => {
        const next = applyDoneEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    const onError: Parameters<typeof sendChatQuerySSE>[1]['onError'] = (event) => {
      setStreamingState((prev) => {
        const next = applyErrorEvent(prev, event);
        streamingRef.current = next;
        return next;
      });
    };

    try {
      // Try SSE first; B2: read conversationIdRef.current instead of stale closed-over state
      const usedSSE = await sendChatQuerySSE(
        { query: question, conversation_id: conversationIdRef.current || undefined },
        { onStep, onAgencies, onIntent, onRouting, onAgencyStart, onAgencyResponded, onAgencyVerified, onAnswer, onDone, onError },
        abortController.signal,
      );

      if (abortController.signal.aborted) return;

      if (usedSSE) {
        finalizeStreaming();
        return;
      }

      // Fallback: regular JSON POST; B2: read conversationIdRef.current for consistency
      const response = await sendChatQuery({ query: question, conversation_id: conversationIdRef.current || undefined });

      if (response.success) {
        setConversationId(response.conversation_id);
        conversationIdRef.current = response.conversation_id;
        setCurrentSteps(response.data.agentSteps as AgentStep[]);
        setActiveStepCount(response.data.agentSteps.length);

        const aiMsgId = response.data.message_id || generateUniqueId();
        const aiMsg: ChatMessage = {
          id: aiMsgId,
          role: 'assistant',
          content: response.data.answer,
          timestamp: formatTimestamp(),
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
      // B8: reset stale streaming state so pipeline steps don't leak into the next send
      setStreamingState(INITIAL_STREAMING_STATE);
      streamingRef.current = INITIAL_STREAMING_STATE;
      setMessages((prev) => [...prev, buildGenericErrorMessage()]);
    }
  }, [input, isTyping, finalizeStreaming]);

  const reset = useCallback(() => {
    setMessages([]);
    setIsTyping(false);
    setActiveStepCount(0);
    setInput('');
    setCurrentSteps(mockAgentSteps);
    setConversationId(null);
    conversationIdRef.current = null;
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
