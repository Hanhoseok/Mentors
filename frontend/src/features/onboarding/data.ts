import type {
  ExperienceLevel,
  InterestTag,
  LearningGoal,
  MentorProfile,
  PreferredStyle,
  RiskProfile,
  SelectOption,
} from './types';

export const experienceLevelOptions: SelectOption<ExperienceLevel>[] = [
  {
    value: 'beginner',
    label: '완전 입문',
    description: '용어가 아직 낯설고, 천천히 기초부터 잡고 싶어요.',
  },
  {
    value: 'exploring',
    label: '탐색 중',
    description: '기사나 차트를 조금 보지만 아직 내 기준은 없어요.',
  },
  {
    value: 'confident',
    label: '직접 판단 가능',
    description: '이미 관심 종목과 시장 이슈를 스스로 찾아보고 있어요.',
  },
];

export const interestOptions: SelectOption<InterestTag>[] = [
  {
    value: 'macro',
    label: '거시 흐름',
    description: '금리, 환율, 경기 같은 큰 흐름을 이해하고 싶어요.',
  },
  {
    value: 'dividend',
    label: '배당과 현금흐름',
    description: '꾸준한 현금흐름과 안정성을 먼저 보고 싶어요.',
  },
  {
    value: 'value',
    label: '가치 판단',
    description: '좋은 회사를 싸게 사는 기준을 배우고 싶어요.',
  },
  {
    value: 'tech',
    label: '기술 성장주',
    description: '빠르게 성장하는 산업과 기업을 추적하고 싶어요.',
  },
  {
    value: 'etf',
    label: 'ETF와 분산',
    description: '한 종목보다 포트폴리오 전체를 안정적으로 짜고 싶어요.',
  },
  {
    value: 'global',
    label: '해외 시장',
    description: '미국과 글로벌 시장까지 시야를 넓히고 싶어요.',
  },
];

export const riskProfileOptions: SelectOption<RiskProfile>[] = [
  { value: 'steady', label: '안정 우선', description: '손실을 크게 피하면서 천천히 가고 싶어요.' },
  {
    value: 'balanced',
    label: '균형 추구',
    description: '안정성과 기회를 적절히 함께 보고 싶어요.',
  },
  {
    value: 'bold',
    label: '기회 선호',
    description: '변동성이 있어도 성장을 더 빠르게 보고 싶어요.',
  },
];

export const learningGoalOptions: SelectOption<LearningGoal>[] = [
  {
    value: 'build-habit',
    label: '루틴 만들기',
    description: '매일 무엇을 보면 되는지 감을 잡고 싶어요.',
  },
  {
    value: 'understand-news',
    label: '뉴스 해석',
    description: '뉴스를 보면 왜 중요한지 바로 연결하고 싶어요.',
  },
  {
    value: 'find-style',
    label: '내 스타일 찾기',
    description: '어떤 투자 방식이 나와 맞는지 탐색하고 싶어요.',
  },
];

export const preferredStyleOptions: SelectOption<PreferredStyle>[] = [
  {
    value: 'gentle',
    label: '부드럽게',
    description: '불안하지 않게 쉽게 풀어서 설명해 주면 좋아요.',
  },
  {
    value: 'structured',
    label: '체계적으로',
    description: '원리, 체크포인트, 다음 액션이 분명하면 좋아요.',
  },
  {
    value: 'challenging',
    label: '단단하게',
    description: '생각할 거리를 던져주고 조금은 밀어붙여도 괜찮아요.',
  },
];

export const mentorCatalog: MentorProfile[] = [
  {
    id: 'soohyun',
    name: '수현 멘토',
    title: '차분한 배당 설계자',
    oneLiner: '불안을 낮추고, 작은 습관부터 투자 체력을 쌓게 도와주는 멘토',
    philosophy: '흔들릴수록 기준은 더 단순해야 해요. 이해한 것만 천천히 쌓아 갑니다.',
    idealFor: '처음 시작하는 입문자, 안정적인 기준이 먼저 필요한 사용자',
    accentColor: '#0D6A57',
    focusTags: ['dividend', 'value', 'etf', 'macro'],
    experienceMatch: ['beginner', 'exploring'],
    riskMatch: ['steady', 'balanced'],
    styleMatch: ['gentle', 'structured'],
    goalMatch: ['build-habit', 'understand-news'],
    strengths: ['기초 용어를 쉽게 설명', '루틴 중심 학습', '안정적인 시각 유지'],
  },
  {
    id: 'minjae',
    name: '민재 멘토',
    title: '구조를 읽는 매크로 해설가',
    oneLiner: '뉴스, 지표, ETF를 연결해서 전체 그림을 잡아주는 멘토',
    philosophy: '개별 종목보다 먼저 시장의 구조를 읽으면 흔들림이 줄어들어요.',
    idealFor: '뉴스 해석과 분산 투자 기준을 잡고 싶은 사용자',
    accentColor: '#355CDE',
    focusTags: ['macro', 'etf', 'global', 'value'],
    experienceMatch: ['exploring', 'confident'],
    riskMatch: ['steady', 'balanced', 'bold'],
    styleMatch: ['structured', 'challenging'],
    goalMatch: ['understand-news', 'find-style'],
    strengths: ['뉴스 해석 연결', 'ETF/거시 프레임 제공', '질문으로 사고 확장'],
  },
  {
    id: 'jiwoo',
    name: '지우 멘토',
    title: '성장 기회를 좇는 트렌드 스카우트',
    oneLiner: '빠르게 변하는 산업과 성장 서사를 흥미롭게 읽어주는 멘토',
    philosophy: '기회는 늘 새롭게 생겨요. 다만 왜 오르는지 끝까지 설명할 수 있어야 해요.',
    idealFor: '기술주와 성장 산업에 흥미가 크고, 자기 스타일을 찾고 싶은 사용자',
    accentColor: '#C66B5A',
    focusTags: ['tech', 'global', 'macro'],
    experienceMatch: ['beginner', 'exploring', 'confident'],
    riskMatch: ['balanced', 'bold'],
    styleMatch: ['gentle', 'challenging'],
    goalMatch: ['find-style', 'understand-news'],
    strengths: ['트렌드 맥락 설명', '성장 서사 전달', '몰입감 있는 코칭'],
  },
];

function getOptionLabel<T extends string>(
  options: SelectOption<T>[],
  value: T | null | undefined,
): string {
  return options.find((option) => option.value === value)?.label ?? '';
}

export function getExperienceLevelLabel(value: ExperienceLevel | null | undefined): string {
  return getOptionLabel(experienceLevelOptions, value);
}

export function getInterestLabel(value: InterestTag): string {
  return getOptionLabel(interestOptions, value);
}

export function getRiskProfileLabel(value: RiskProfile | null | undefined): string {
  return getOptionLabel(riskProfileOptions, value);
}

export function getLearningGoalLabel(value: LearningGoal | null | undefined): string {
  return getOptionLabel(learningGoalOptions, value);
}

export function getPreferredStyleLabel(value: PreferredStyle | null | undefined): string {
  return getOptionLabel(preferredStyleOptions, value);
}
