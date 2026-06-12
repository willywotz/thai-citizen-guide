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
  const abortRef = useRef<AbortController | null>(null);
  // Ref to always have latest streaming state in closures
  const streamingRef = useRef<StreamingState>(INITIAL_STREAMING_STATE);

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
    state.sessionId && setConversationId(state.sessionId);
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
    const applyAndSet = <E>(applyFn: (prev: StreamingState, event: E) => StreamingState) =>
      (event: E) => {
        const next = applyFn(streamingRef.current, event);
        streamingRef.current = next;
        setStreamingState(next);
      };

    const onStep = applyAndSet(applyStepEvent);
    const onAgencies = applyAndSet(applyAgenciesEvent);
    const onIntent = applyAndSet(applyIntentEvent);
    const onRouting = applyAndSet(applyRoutingEvent);
    const onAgencyStart = applyAndSet(applyAgencyStartEvent);
    const onAgencyResponded = applyAndSet(applyAgencyRespondedEvent);
    const onAgencyVerified = applyAndSet(applyAgencyVerifiedEvent);
    const onAnswer = applyAndSet(applyAnswerEvent);
    const onDone = applyAndSet(applyDoneEvent);
    const onError = applyAndSet(applyErrorEvent);

    try {
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
