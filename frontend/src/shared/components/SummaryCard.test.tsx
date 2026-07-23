import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SummaryCard } from './SummaryCard';

describe('SummaryCard', () => {
  it('renders the summary text and numbered references', () => {
    render(
      <SummaryCard
        summary="ค่าธรรมเนียมอยู่ที่ 2% [1]"
        references={[{ number: 1, agency_id: 'land', agency_name: 'กรมที่ดิน', url: null }]}
      />,
    );
    expect(screen.getByText(/ค่าธรรมเนียมอยู่ที่ 2%/)).toBeInTheDocument();
    expect(screen.getByText(/\[1\] กรมที่ดิน/)).toBeInTheDocument();
  });

  it('renders nothing without a summary', () => {
    const { container } = render(<SummaryCard summary={null} references={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for a blank summary', () => {
    const { container } = render(<SummaryCard summary="   " />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the summary without a reference list when there are no references', () => {
    render(<SummaryCard summary="สรุปสั้นๆ" />);
    expect(screen.getByText('สรุปสั้นๆ')).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });
});
