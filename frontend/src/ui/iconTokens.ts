export type AppIconName =
  | 'account-circle'
  | 'airplane'
  | 'antenna'
  | 'battery-high'
  | 'bell'
  | 'bell-badge'
  | 'bell-off-outline'
  | 'bookmark'
  | 'briefcase'
  | 'car'
  | 'cart'
  | 'cellphone'
  | 'chart-box'
  | 'check-circle'
  | 'compass'
  | 'file-document'
  | 'flash'
  | 'flask'
  | 'folder'
  | 'leaf'
  | 'lock'
  | 'message-text'
  | 'movie-open'
  | 'newspaper-variant-outline'
  | 'open-in-new'
  | 'school'
  | 'shield-half-full'
  | 'shopping'
  | 'ship-wheel'
  | 'sword-cross'
  | 'water'
  | 'wrench';

export type HeaderActionKey = 'notifications' | 'scrap' | 'settings';
export type TabIconKey = 'Search' | 'MentorChat' | 'DebateArena';

const TAB_ICON_NAMES: Record<TabIconKey, AppIconName> = {
  Search: 'compass',
  MentorChat: 'message-text',
  DebateArena: 'sword-cross',
};

const HEADER_ACTION_ICON_NAMES: Record<HeaderActionKey, AppIconName> = {
  notifications: 'bell-badge',
  scrap: 'bookmark',
  settings: 'account-circle',
};

const NOTIFICATION_TYPE_ICON_NAMES: Record<string, AppIconName> = {
  daily_report: 'chart-box',
  promotion_test: 'school',
};

const INDUSTRY_ICON_NAMES: Record<string, AppIconName> = {
  IT기술: 'briefcase',
  화학: 'flask',
  화장품: 'shopping',
  통신: 'antenna',
  탄소저감: 'leaf',
  종이: 'file-document',
  조선: 'ship-wheel',
  전자부품: 'flash',
  전력에너지: 'flash',
  자동차: 'car',
  의류: 'shopping',
  의료: 'briefcase',
  음식료: 'cart',
  유통: 'cart',
  원유: 'flash',
  운송: 'car',
  엔터테인먼트: 'movie-open',
  스마트폰: 'cellphone',
  여행: 'airplane',
  수자원: 'water',
  배터리: 'battery-high',
  반도체: 'chart-box',
  방위산업물자: 'shield-half-full',
  생활용품: 'shopping',
  바이오: 'flask',
  리츠: 'briefcase',
  디스플레이: 'cellphone',
  기계: 'wrench',
  농업: 'leaf',
  금융: 'chart-box',
  금속: 'wrench',
  교육: 'school',
};

export function getTabIconName(name: TabIconKey): AppIconName {
  return TAB_ICON_NAMES[name];
}

export function getHeaderActionIconName(name: HeaderActionKey): AppIconName {
  return HEADER_ACTION_ICON_NAMES[name];
}

export function getNotificationTypeIconName(type: string): AppIconName {
  return NOTIFICATION_TYPE_ICON_NAMES[type] ?? 'bell-badge';
}

export function getIndustryIconName(name: string): AppIconName {
  return INDUSTRY_ICON_NAMES[name] ?? 'bookmark';
}
