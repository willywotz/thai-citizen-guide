import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageItem } from './MessageItem';
import type { ConversationMessage } from '@/shared/types';

const SUMMARY = 'ค่าธรรมเนียมอยู่ที่ 2% [1]';

function msg(overrides: Partial<ConversationMessage> = {}): ConversationMessage {
  return {
    id: 'm1',
    role: 'assistant',
    content: `${SUMMARY}\n\n---\n\nเนื้อหาดิบจากหน่วยงาน`,
    agent_steps: [],
    sources: [],
    rating: null,
    created_at: '2026-07-21T00:00:00Z',
    ...overrides,
  };
}

describe('MessageItem v5 summary', () => {
  it('shows a stored summary once, above the body', () => {
    render(
      <MessageItem
        msg={msg({
          summary: SUMMARY,
          summary_references: [{ number: 1, agency_id: 'land', agency_name: 'กรมที่ดิน', url: null }],
        })}
      />,
    );
    expect(screen.getAllByText(/ค่าธรรมเนียมอยู่ที่ 2%/)).toHaveLength(1);
    expect(screen.getByText('เนื้อหาดิบจากหน่วยงาน')).toBeInTheDocument();
  });

  it('renders pre-v5 messages unchanged', () => {
    render(<MessageItem msg={msg({ content: 'คำตอบเก่า' })} />);
    expect(screen.getByText('คำตอบเก่า')).toBeInTheDocument();
  });
});
