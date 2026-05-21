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
    mentor: '워런 버핏',
    date: '오늘',
    title: '삼성전자 3% 상승, 반도체 업황 회복',
    summary: '오늘의 주가 상승 배경과 PER 관점의 해석',
    understanding: 'known',
  },
  {
    id: 'report-2',
    mentor: '워런 버핏',
    date: '어제',
    title: '기업의 해자(MOAT)란 무엇인가',
    summary: '장기 보유 가치투자의 핵심 — 경쟁 우위 분석',
    understanding: 'heard',
  },
  {
    id: 'report-3',
    mentor: '벤저민 그레이엄',
    date: '3일 전',
    title: '청산가치와 안전마진의 개념',
    summary: '보수적 가치평가 기준과 투자 의사결정',
    understanding: 'unknown',
  },
];

export const arenaRecords: ArenaRecord[] = [
  {
    id: 'arena-1',
    date: '오늘',
    topicLabel: '토론 주제',
    topic: '실적 시즌에 더 주목해야 할 신호는?',
    mentorALetter: 'W',
    mentorBLetter: 'P',
    mentorALabel: '버핏',
    mentorBLabel: '린치',
  },
  {
    id: 'arena-2',
    date: '어제',
    topicLabel: '토론 주제',
    topic: 'ETF 분산이 항상 개별주보다 유리할까요?',
    mentorALetter: 'R',
    mentorBLetter: 'W',
    mentorALabel: '달리오',
    mentorBLabel: '버핏',
  },
  {
    id: 'arena-3',
    date: '3일 전',
    topicLabel: '토론 주제',
    topic: '성장주 조정장에서 현금 비중을 늘려야 할까요?',
    mentorALetter: 'P',
    mentorBLetter: 'R',
    mentorALabel: '린치',
    mentorBLabel: '달리오',
  },
  {
    id: 'arena-4',
    date: '1주 전',
    topicLabel: '토론 주제',
    topic: '배당주는 금리 하락 국면에서 어떤 매력이 있을까요?',
    mentorALetter: 'W',
    mentorBLetter: 'R',
    mentorALabel: '버핏',
    mentorBLabel: '달리오',
  },
];
