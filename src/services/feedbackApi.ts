import { api } from '@/lib/apiClient';

export async function updateMessageRating(
  messageId: string,
  rating: 'up' | 'down',
  feedbackText?: string
): Promise<boolean> {
  try {
    const body: Record<string, any> = { rating };
    if (feedbackText !== undefined) {
      body.feedback_text = feedbackText;
    }
    await api.patch(`/api/conversations/messages/${messageId}/rating`, body);
    return true;
  } catch (err) {
    console.warn('Failed to update rating:', err);
    return false;
  }
}

export interface FeedbackStats {
  totalRatings: number;
  upCount: number;
  downCount: number;
  satisfactionRate: number;
  dailyTrend: { date: string; up: number; down: number; rate: number }[];
  lowRatedQuestions: { content: string; feedback_text: string | null; agency: string; created_at: string }[];
  agencyBreakdown: { agency: string; up: number; down: number; rate: number }[];
}

export async function fetchFeedbackStats(): Promise<FeedbackStats> {
  try {
    return await api.get<FeedbackStats>('/api/feedback/stats');
  } catch {
    console.warn('Feedback stats API failed, using empty data');
    return {
      totalRatings: 0,
      upCount: 0,
      downCount: 0,
      satisfactionRate: 0,
      dailyTrend: [],
      lowRatedQuestions: [],
      agencyBreakdown: [],
    };
  }
}
