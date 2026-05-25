export type ReportUnderstanding = 'known' | 'heard' | 'unknown';

export interface ReportRecord {
  id: string;
  mentor: string;
  date: string;
  title: string;
  summary: string;
  understanding: ReportUnderstanding;
}

export interface ArenaRecord {
  id: string;
  date: string;
  topicLabel: string;
  topic: string;
  mentorALetter: string;
  mentorBLetter: string;
  mentorALabel: string;
  mentorBLabel: string;
}

export const reportRecords: ReportRecord[] = [
  {
    id: 'report-1',
    mentor: 'Warren Buffett',
    date: 'Today',
    title: 'Samsung Electronics rises 3% as chip sentiment improves',
    summary: 'A quick read of the rally through earnings and valuation context.',
    understanding: 'known',
  },
  {
    id: 'report-2',
    mentor: 'Warren Buffett',
    date: 'Yesterday',
    title: 'What is a business moat?',
    summary: 'A beginner-friendly take on durable advantages and long-term investing.',
    understanding: 'heard',
  },
  {
    id: 'report-3',
    mentor: 'Benjamin Graham',
    date: '3 days ago',
    title: 'Liquidation value and margin of safety',
    summary: 'A conservative framework for valuation and downside protection.',
    understanding: 'unknown',
  },
];

export const arenaRecords: ArenaRecord[] = [
  {
    id: 'arena-1',
    date: 'Today',
    topicLabel: 'Debate topic',
    topic: 'Which signal matters more during earnings season?',
    mentorALetter: 'W',
    mentorBLetter: 'P',
    mentorALabel: 'Buffett',
    mentorBLabel: 'Lynch',
  },
  {
    id: 'arena-2',
    date: 'Yesterday',
    topicLabel: 'Debate topic',
    topic: 'Is ETF diversification always better than picking stocks?',
    mentorALetter: 'R',
    mentorBLetter: 'W',
    mentorALabel: 'Dalio',
    mentorBLabel: 'Buffett',
  },
  {
    id: 'arena-3',
    date: '3 days ago',
    topicLabel: 'Debate topic',
    topic: 'Should you raise cash during a growth stock correction?',
    mentorALetter: 'P',
    mentorBLetter: 'R',
    mentorALabel: 'Lynch',
    mentorBLabel: 'Dalio',
  },
  {
    id: 'arena-4',
    date: '1 week ago',
    topicLabel: 'Debate topic',
    topic: 'What makes dividend stocks attractive when rates are falling?',
    mentorALetter: 'W',
    mentorBLetter: 'R',
    mentorALabel: 'Buffett',
    mentorBLabel: 'Dalio',
  },
];
