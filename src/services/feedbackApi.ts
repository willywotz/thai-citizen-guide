import { supabase } from '@/integrations/supabase/client';

export async function updateMessageRating(
  messageId: string,
  rating: 'up' | 'down',
  feedbackText?: string
): Promise<boolean> {
  try {
    const updateData: Record<string, any> = { rating };
    if (feedbackText !== undefined) {
      updateData.feedback_text = feedbackText;
    }

    const { error } = await supabase
      .from('messages')
      .update(updateData as any)
      .eq('id', messageId);

    if (error) throw error;
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
    const { data, error } = await supabase.functions.invoke('feedback-stats');
    if (error) throw error;
    return data as FeedbackStats;
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
