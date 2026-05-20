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
    id: 1,
    slug: 'warren-buffett',
    name: 'Warren Buffett',
    title: 'Value Investing Mentor',
    oneLiner: '장기 복리, 기업 가치, 기다림의 힘을 기초부터 차분히 잡아주는 멘토',
    philosophy: '좋은 기업을 이해한 뒤 오래 들고 가는 힘이 결국 큰 차이를 만든다고 봅니다.',
    idealFor: '안정적으로 투자 기초를 쌓고 장기 관점의 판단 기준을 만들고 싶은 사용자',
    accentColor: '#0D6A57',
    focusTags: ['dividend', 'value', 'etf', 'macro'],
    experienceMatch: ['beginner', 'exploring'],
    riskMatch: ['steady', 'balanced'],
    styleMatch: ['gentle', 'structured'],
    goalMatch: ['build-habit', 'understand-news'],
    strengths: ['가치 투자 기초', '장기 복리 관점', '안정적인 투자 습관'],
  },
  {
    id: 2,
    slug: 'peter-lynch',
    name: 'Peter Lynch',
    title: 'Everyday Stock Picking Mentor',
    oneLiner: 'Company-first research with practical examples and accessible explanations.',
    philosophy: '생활 속에서 이해한 기업을 꾸준히 관찰하면 좋은 아이디어는 가까이에 있다고 봅니다.',
    idealFor: '뉴스와 기업 사례를 연결해서 개별 종목 감각을 키우고 싶은 사용자',
    accentColor: '#C66B5A',
    focusTags: ['value', 'tech', 'global', 'dividend'],
    experienceMatch: ['beginner', 'exploring', 'confident'],
    riskMatch: ['balanced', 'bold'],
    styleMatch: ['gentle', 'challenging'],
    goalMatch: ['find-style', 'understand-news'],
    strengths: ['생활밀착형 기업 분석', '쉬운 사례 중심 설명', '성장주 감각 키우기'],
  },
  {
    id: 3,
    slug: 'ray-dalio',
    name: 'Ray Dalio',
    title: 'Macro and Portfolio Mentor',
    oneLiner: '거시 흐름, 분산, 포트폴리오 관점을 구조적으로 설명해주는 멘토',
    philosophy: '개별 종목보다 먼저 큰 흐름과 자산 배분을 읽으면 흔들림이 줄어든다고 봅니다.',
    idealFor: '뉴스 해석과 분산 투자 기준을 함께 세우고 싶은 사용자',
    accentColor: '#355CDE',
    focusTags: ['macro', 'etf', 'global', 'value'],
    experienceMatch: ['exploring', 'confident'],
    riskMatch: ['steady', 'balanced', 'bold'],
    styleMatch: ['structured', 'challenging'],
    goalMatch: ['understand-news', 'build-habit', 'find-style'],
    strengths: ['거시 흐름 해석', '포트폴리오 시야', '구조적인 설명'],
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
