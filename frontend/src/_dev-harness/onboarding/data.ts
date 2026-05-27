import type {
  ExperienceLevel,
  InterestTag,
  LearningGoal,
  MentorProfile,
  PreferredStyle,
  RiskProfile,
  SelectOption,
} from '../../features/onboarding/types';

export const experienceLevelOptions: SelectOption<ExperienceLevel>[] = [
  {
    value: 'beginner',
    label: '완전 입문',
    description: '용어가 아직 낯설고 차근차근 기초부터 쌓고 싶어요.',
  },
  {
    value: 'exploring',
    label: '탐색 중',
    description: '기사와 차트를 조금 보지만 아직 나만의 기준은 없어요.',
  },
  {
    value: 'confident',
    label: '직접 판단 가능',
    description: '관심 종목과 시장 이슈를 스스로 찾아보며 비교하고 있어요.',
  },
];

export const interestOptions: SelectOption<InterestTag>[] = [
  {
    value: 'macro',
    label: '거시 흐름',
    description: '금리, 환율, 경기 흐름 같은 큰 맥락을 이해하고 싶어요.',
  },
  {
    value: 'dividend',
    label: '배당과 현금흐름',
    description: '꾸준한 현금흐름과 안정적인 투자 습관을 먼저 만들고 싶어요.',
  },
  {
    value: 'value',
    label: '가치 판단',
    description: '좋은 회사를 어떻게 찾는지 기업의 본질부터 배우고 싶어요.',
  },
  {
    value: 'tech',
    label: '반도체·AI',
    description: '반도체, AI 인프라, 첨단 기술 흐름을 따라가며 핵심 종목을 보고 싶어요.',
  },
  {
    value: 'it',
    label: 'IT·테크',
    description: '소프트웨어, 플랫폼, 인터넷 서비스 기업을 중심으로 배우고 싶어요.',
  },
  {
    value: 'bio',
    label: '바이오',
    description: '제약, 바이오, 의료기기처럼 성장성과 이슈가 큰 분야를 이해하고 싶어요.',
  },
  {
    value: 'etf',
    label: 'ETF·펀드',
    description: '개별 종목보다 포트폴리오 전체를 안정적으로 보고 싶어요.',
  },
  {
    value: 'global',
    label: '해외 주식',
    description: '미국과 글로벌 시장까지 시야를 넓히고 싶어요.',
  },
];

export const profileInterestOptions: SelectOption<InterestTag>[] = [
  {
    value: 'domestic-stock',
    label: '국내 주식',
    description: '국내 대표 기업과 산업 흐름을 중심으로 배우고 싶어요.',
  },
  {
    value: 'us-stock',
    label: '미국 주식',
    description: '미국 빅테크와 대표 지수 중심으로 시장을 이해하고 싶어요.',
  },
  {
    value: 'global',
    label: '해외 주식',
    description: '미국 외 글로벌 종목과 지역별 시장 흐름도 함께 보고 싶어요.',
  },
  {
    value: 'bio',
    label: '바이오',
    description: '제약, 바이오, 헬스케어 산업의 성장성과 이슈를 따라가고 싶어요.',
  },
  {
    value: 'it',
    label: 'IT·테크',
    description: '플랫폼, 소프트웨어, 인터넷 서비스 기업을 중심으로 배우고 싶어요.',
  },
  {
    value: 'semiconductor',
    label: '반도체',
    description: '반도체 업황과 핵심 부품·장비 기업을 이해하고 싶어요.',
  },
  {
    value: 'battery',
    label: '2차전지',
    description: '배터리 소재, 셀, 장비 산업의 흐름을 보고 싶어요.',
  },
  {
    value: 'ai',
    label: 'AI',
    description: 'AI 서비스와 인프라 시장이 어떤 산업을 움직이는지 궁금해요.',
  },
  {
    value: 'defense',
    label: '방산',
    description: '지정학 이슈와 연결되는 방위산업 흐름을 알고 싶어요.',
  },
  {
    value: 'energy',
    label: '에너지',
    description: '원유, 전력, 친환경 에너지 섹터를 중심으로 이해하고 싶어요.',
  },
  {
    value: 'finance',
    label: '금융',
    description: '은행, 보험, 증권 업종이 금리와 함께 어떻게 움직이는지 보고 싶어요.',
  },
  {
    value: 'entertainment-media',
    label: '엔터·미디어',
    description: '콘텐츠, 플랫폼, 팬덤 비즈니스가 주가와 연결되는 방식을 보고 싶어요.',
  },
  {
    value: 'fashion-consumer',
    label: '패션·소비재',
    description: '브랜드, 유통, 소비 트렌드 중심으로 기업을 이해하고 싶어요.',
  },
  {
    value: 'etf',
    label: 'ETF·펀드',
    description: '개별 종목보다 포트폴리오 전체를 안정적으로 보고 싶어요.',
  },
  {
    value: 'crypto',
    label: '암호화폐',
    description: '코인 시장과 관련 주식, 정책 이슈를 함께 이해하고 싶어요.',
  },
];

export const onboardingInterestOptions = profileInterestOptions;

export const riskProfileOptions: SelectOption<RiskProfile>[] = [
  {
    value: 'steady',
    label: '안정 우선',
    description: '크게 흔들리지 않으면서 천천히 가고 싶어요.',
  },
  {
    value: 'balanced',
    label: '균형 추구',
    description: '안정감과 기회를 적절하게 함께 보고 싶어요.',
  },
  {
    value: 'bold',
    label: '기회 선호',
    description: '변동성이 있어도 성장 가능성을 더 빠르게 보고 싶어요.',
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
    label: '내 투자 스타일 찾기',
    description: '어떤 투자 방식이 나에게 맞는지 탐색하고 싶어요.',
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
    description: '정리, 체크포인트, 다음 액션이 분명하면 좋아요.',
  },
  {
    value: 'challenging',
    label: '단단하게',
    description: '생각할 거리를 던져 주고 조금 더 밀어붙여도 괜찮아요.',
  },
];

export const mentorCatalog: MentorProfile[] = [
  {
    id: 1,
    slug: 'warren-buffett',
    name: '워런 버핏',
    title: '가치 투자 멘토',
    oneLiner: '장기 복리와 기업 가치의 기본을 차분히 잡아주는 가치투자 멘토',
    philosophy:
      '좋은 기업을 제대로 이해하고 오래 보유하는 태도가 결국 복리의 차이를 만든다고 봅니다.',
    idealFor: '안정적인 투자 기초를 쌓고 장기 관점의 판단 기준을 만들고 싶은 사용자',
    accentColor: '#2D6A4F',
    focusTags: ['dividend', 'value', 'etf', 'macro', 'domestic-stock', 'us-stock', 'finance'],
    experienceMatch: ['beginner', 'exploring'],
    riskMatch: ['steady', 'balanced'],
    styleMatch: ['gentle', 'structured'],
    goalMatch: ['build-habit', 'understand-news'],
    strengths: ['가치투자 기초', '장기 복리 관점', '안정적인 투자 습관'],
  },
  {
    id: 2,
    slug: 'peter-lynch',
    name: '피터 린치',
    title: '생활형 종목 발굴 멘토',
    oneLiner: '생활 속 단서와 쉬운 설명으로 종목 판단 감각을 키워주는 멘토',
    philosophy: '생활 속에서 이해한 기업을 꾸준히 관찰하면 좋은 아이디어는 가까이에 있다고 봅니다.',
    idealFor: '뉴스와 기업 사례를 연결해서 개별 종목 감각을 키우고 싶은 사용자',
    accentColor: '#C66B5A',
    focusTags: [
      'value',
      'tech',
      'it',
      'bio',
      'global',
      'dividend',
      'domestic-stock',
      'us-stock',
      'semiconductor',
      'battery',
      'ai',
      'entertainment-media',
      'fashion-consumer',
    ],
    experienceMatch: ['beginner', 'exploring', 'confident'],
    riskMatch: ['balanced', 'bold'],
    styleMatch: ['gentle', 'challenging'],
    goalMatch: ['find-style', 'understand-news'],
    strengths: ['생활밀착형 기업 분석', '쉬운 사례 중심 설명', '성장주 감각 키우기'],
  },
  {
    id: 3,
    slug: 'ray-dalio',
    name: '레이 달리오',
    title: '거시 흐름과 포트폴리오 멘토',
    oneLiner: '거시 흐름과 분산 관점을 구조적으로 설명해 주는 포트폴리오 멘토',
    philosophy: '개별 종목보다 먼저 큰 흐름과 자산 배분을 이해하면 흔들림이 줄어든다고 봅니다.',
    idealFor: '뉴스 해석과 분산 투자 기준을 함께 세우고 싶은 사용자',
    accentColor: '#355CDE',
    focusTags: ['macro', 'etf', 'global', 'value', 'tech', 'it', 'energy', 'finance', 'us-stock'],
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
  return getOptionLabel(profileInterestOptions, value) || getOptionLabel(interestOptions, value);
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
