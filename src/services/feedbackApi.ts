import { apiGet, apiPatch } from './apiClient';

export async function updateMessageRating(
  conversationId: string,
  messageId: string,
  rating: 'up' | 'down',
  feedbackText?: string
): Promise<boolean> {
  try {
    await apiPatch(`/conversations/${conversationId}/messages/${messageId}/rating`, {
      rating,
      feedback_text: feedbackText,
    });
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
    const res = await apiGet<{ success: boolean; data: FeedbackStats }>('/feedback/stats');
    return res.data;
  } catch {
    console.warn('Feedback stats API failed, using empty data');
    return {
      totalRatings: 0, upCount: 0, downCount: 0, satisfactionRate: 0,
      dailyTrend: [], lowRatedQuestions: [], agencyBreakdown: [],
    };
  }
}
