import type { ExperienceLevel, InterestTag, LearningGoal, RiskProfile } from '../types';

export interface AgeOption {
  value: string;
  label: string;
}

export const ageOptions: AgeOption[] = [
  { value: 'teens', label: '10대' },
  { value: 'early20s', label: '20대 초반 (20~24세)' },
  { value: 'late20s', label: '20대 후반 (25~29세)' },
  { value: 'thirties', label: '30대' },
  { value: 'fortiesPlus', label: '40대 이상' },
];

export interface ExperienceOption {
  value: ExperienceLevel;
  label: string;
  description: string;
}

export const experienceOptions: ExperienceOption[] = [
  {
    value: 'beginner',
    label: '없어요, 처음이에요',
    description: '용어가 아직 낯설고 차근차근 기초부터 쌓고 싶어요.',
  },
  {
    value: 'exploring',
    label: '조금 해봤어요',
    description: '기사와 차트를 조금 보지만 아직 나만의 기준은 없어요.',
  },
  {
    value: 'confident',
    label: '꽤 경험이 있어요',
    description: '관심 종목과 시장 이슈를 스스로 찾아보며 비교하고 있어요.',
  },
];

export interface GoalOption {
  value: string;
  label: string;
}

export const goalOptions: GoalOption[] = [
  { value: 'wealth', label: '재테크·자산 불리기' },
  { value: 'retirement', label: '노후 준비' },
  { value: 'social', label: '주변 사람들의 영향' },
  { value: 'study', label: '경제 공부가 하고 싶어서' },
  { value: 'other', label: '기타' },
];

export interface ScaleOption {
  value: string;
  label: string;
}

export const scaleOptions: ScaleOption[] = [
  { value: 'under1m', label: '100만원 미만' },
  { value: '1m_to_5m', label: '100~500만원' },
  { value: '5m_to_10m', label: '500~1000만원' },
  { value: 'over10m', label: '1000만원 이상' },
  { value: 'none', label: '아직 없어요' },
];

export interface RiskOption {
  value: RiskProfile;
  label: string;
  description: string;
}

export const riskOptions: RiskOption[] = [
  {
    value: 'steady',
    label: '손실 없이 안정적으로만',
    description: '크게 흔들리지 않으면서 천천히 가고 싶어요.',
  },
  {
    value: 'balanced',
    label: '5~10% 정도는 괜찮아요',
    description: '안정감과 기회를 적절하게 함께 보고 싶어요.',
  },
  {
    value: 'bold',
    label: '20~30% 정도도 감수 가능',
    description: '변동성이 있어도 성장 가능성을 더 빠르게 보고 싶어요.',
  },
];

export interface InterestCategory {
  name: string;
  emoji: string;
  backendTag: InterestTag;
  children: string[];
}

export const interestCategories: InterestCategory[] = [
  {
    name: 'IT tech',
    emoji: '💻',
    backendTag: 'it',
    children: [
      '보안',
      '소프트웨어',
      '양자컴퓨터',
      '인공지능',
      '인터넷',
      '클라우드',
      'IT솔루션 구축',
    ],
  },
  {
    name: '반도체',
    emoji: '💾',
    backendTag: 'semiconductor',
    children: [
      '반도체 부품소재',
      '반도체 장비',
      '반도체 파운드리',
      '반도체패키징',
      '반도체팹리스',
      '종합반도체',
    ],
  },
  {
    name: '배터리',
    emoji: '🔋',
    backendTag: 'battery',
    children: ['배터리부품', '배터리소재', '배터리장비', '배터리제조', '폐배터리재활용'],
  },
  {
    name: '바이오',
    emoji: '🧬',
    backendTag: 'bio',
    children: ['바이오서비스', '바이오시밀러', '바이오신약'],
  },
  {
    name: '금융',
    emoji: '💵',
    backendTag: 'finance',
    children: [
      '결제서비스',
      '금융그룹',
      '금융기기',
      '금융상품거래소',
      '벤처캐피탈',
      '보험',
      '신용평가',
      '암호화폐',
      '은행',
      '증권',
      '카드',
    ],
  },
  {
    name: '엔터테인먼트',
    emoji: '🎬',
    backendTag: 'entertainment-media',
    children: ['광고', '동영상 플랫폼', '방송', '영화', '웹툰', '음원', '출판', '캐릭터'],
  },
  {
    name: '화학',
    emoji: '🧪',
    backendTag: 'energy',
    children: ['비료와 농약', '산업용 가스', '화학원료', '화학제품'],
  },
  {
    name: '전력에너지',
    emoji: '⚡',
    backendTag: 'energy',
    children: ['신재생 에너지', '원자력 발전', '전기설비', '화력발전'],
  },
  {
    name: '원유',
    emoji: '🛢️',
    backendTag: 'energy',
    children: ['원유개발', '원유정제'],
  },
  {
    name: '자동차',
    emoji: '🚗',
    backendTag: 'tech',
    children: [
      '수소차',
      '오토바이',
      '자동차부품',
      '자동차브랜드',
      '자동차유통',
      '전기차',
      '전기차 부품',
    ],
  },
  {
    name: '스마트폰',
    emoji: '📱',
    backendTag: 'tech',
    children: ['스마트폰 부품', '스마트폰 제조'],
  },
  {
    name: '디스플레이',
    emoji: '🖥️',
    backendTag: 'tech',
    children: ['디스플레이 부품 소재', '디스플레이 장비', '디스플레이 패널', 'LED'],
  },
  {
    name: '기계',
    emoji: '⚙️',
    backendTag: 'tech',
    children: ['농업용 기계', '로봇', '산업용기계'],
  },
  {
    name: '조선',
    emoji: '🚢',
    backendTag: 'tech',
    children: ['조선기자재', '조선사'],
  },
  {
    name: '화장품',
    emoji: '💄',
    backendTag: 'fashion-consumer',
    children: ['화장품 브랜드', '화장품제조'],
  },
  {
    name: '의류',
    emoji: '👕',
    backendTag: 'fashion-consumer',
    children: ['섬유', '의류 브랜드', '의류제조'],
  },
  {
    name: '유통',
    emoji: '🛒',
    backendTag: 'fashion-consumer',
    children: ['대형마트', '면세점', '무역', '백화점', '온라인쇼핑', '편의점'],
  },
  {
    name: '생활용품',
    emoji: '🧼',
    backendTag: 'fashion-consumer',
    children: ['그릇', '마스크'],
  },
  {
    name: '음식료',
    emoji: '🍎',
    backendTag: 'fashion-consumer',
    children: [], // No child listed
  },
  {
    name: '통신',
    emoji: '📡',
    backendTag: 'it',
    children: ['이동통신사', '통신장비'],
  },
  {
    name: '의료',
    emoji: '🏥',
    backendTag: 'bio',
    children: ['의료기기', '의료서비스', '제약'],
  },
  {
    name: '리츠',
    emoji: '🏢',
    backendTag: 'etf',
    children: ['상업용리츠', '오피스 리츠', '인프라 리츠', '주거용 리츠'],
  },
  {
    name: '운송',
    emoji: '📦',
    backendTag: 'global',
    children: ['물류', '해상운송', '드론', '항공사', '철도'],
  },
  {
    name: '여행',
    emoji: '✈️',
    backendTag: 'global',
    children: ['렌터카', '여행플랫폼', '카지노', '호텔과 리조트'],
  },
  {
    name: '금속',
    emoji: '🪙',
    backendTag: 'value',
    children: ['광산개발', '구리', '아연', '알루미늄', '철강'],
  },
  {
    name: '교육',
    emoji: '🎓',
    backendTag: 'value',
    children: ['교육서비스', '교육장비', '교육출판'],
  },
  {
    name: '종이',
    emoji: '📄',
    backendTag: 'value',
    children: ['골판지', '백판지'],
  },
  {
    name: '탄소저감',
    emoji: '🍃',
    backendTag: 'global',
    children: ['탄소배출권'],
  },
  {
    name: '전자부품',
    emoji: '🔌',
    backendTag: 'tech',
    children: ['가전부품'],
  },
  {
    name: '수자원',
    emoji: '💧',
    backendTag: 'global',
    children: [],
  },
  {
    name: '방위산업물자',
    emoji: '🛡️',
    backendTag: 'defense',
    children: [],
  },
  {
    name: '농업',
    emoji: '🌾',
    backendTag: 'global',
    children: [],
  },
];

// Helper to map custom survey inputs to backend expected types
export function mapGoalToBackend(goals: string[]): LearningGoal {
  if (goals.includes('study')) {
    return 'understand-news';
  }
  if (goals.includes('wealth') || goals.includes('retirement')) {
    return 'build-habit';
  }
  return 'find-style';
}
