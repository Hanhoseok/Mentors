import { Platform, StyleSheet, View } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import type { MainTabParamList } from './types';
import { SearchScreen } from '@/features/explore/screens/SearchScreen';
import { MentorChatScreen } from '@/features/chat/screens/MentorChatScreen';
import { DebateArenaScreen } from '@/features/debate-arena/screens/DebateArenaScreen';
import { buildMainTabBarMetrics } from './logic';
import { AppIcon } from '@/components/AppIcon';
import { getTabIconName } from '@/ui/iconTokens';

const Tab = createBottomTabNavigator<MainTabParamList>();

const TAB_CONFIG: Record<keyof MainTabParamList, { title: string }> = {
  Search: { title: '탐색' },
  MentorChat: { title: '채팅' },
  DebateArena: { title: '투기장' },
};

function TabIcon({ name, focused }: { name: keyof MainTabParamList; focused: boolean }) {
  return (
    <View style={[styles.tabIconShell, focused && styles.tabIconShellFocused]}>
      <AppIcon
        color={focused ? colors.primary : '#7F8C83'}
        name={getTabIconName(name)}
        size={20}
        style={styles.tabIconGlyph}
      />
    </View>
  );
}

export function MainTabNavigator() {
  const insets = useSafeAreaInsets();
  const tabBarMetrics = buildMainTabBarMetrics({
    bottomInset: insets.bottom,
    platform: Platform.OS === 'ios' ? 'ios' : Platform.OS === 'web' ? 'web' : 'android',
  });

  return (
    <Tab.Navigator
      initialRouteName="Search"
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        // 아이콘+라벨을 항목 안에서 가로·세로 중앙 정렬
        tabBarItemStyle: {
          alignItems: 'center',
          justifyContent: 'center',
        },
        tabBarStyle: {
          position: 'absolute',
          backgroundColor: colors.surface,
          // 바닥에서 살짝 띄운 둥근 카드.
          // 그림자(=모서리 회색 번짐) 완전 제거 + 깔끔한 테두리 선으로 구분/가시성 확보.
          borderWidth: 3,
          borderColor: '#D5D9D5',
          borderRadius: tabBarMetrics.borderRadius,
          marginHorizontal: tabBarMetrics.marginHorizontal,
          marginBottom: tabBarMetrics.marginBottom,
          height: tabBarMetrics.height,
          paddingBottom: tabBarMetrics.paddingBottom,
          paddingTop: tabBarMetrics.paddingTop - 7,
          elevation: 0,
          shadowOpacity: 0,
          shadowColor: 'transparent',
          shadowRadius: 0,
          shadowOffset: { width: 0, height: 0 },
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '700',
          marginTop: 0,
          textAlign: 'center',
        },
      }}
    >
      <Tab.Screen
        name="Search"
        component={SearchScreen}
        options={{
          title: TAB_CONFIG.Search.title,
          tabBarIcon: ({ focused }) => <TabIcon name="Search" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="MentorChat"
        component={MentorChatScreen}
        options={{
          title: TAB_CONFIG.MentorChat.title,
          tabBarIcon: ({ focused }) => <TabIcon name="MentorChat" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="DebateArena"
        component={DebateArenaScreen}
        options={{
          title: TAB_CONFIG.DebateArena.title,
          tabBarIcon: ({ focused }) => <TabIcon name="DebateArena" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabIconShell: {
    alignItems: 'center',
    borderRadius: 14,
    height: 48,
    justifyContent: 'center',
    width: 90,
    transform: [{ translateY: 7 }],   // ← 추가. 숫자가 클수록 아래로 내려감
  },
  tabIconShellFocused: {
    backgroundColor: colors.primarySoft,
  },
  tabIconGlyph: {
    // 박스는 그대로 두고 아이콘만 위로 살짝 올림 (숫자가 클수록 더 올라감)
    transform: [{ translateY: -6 }],
  },
});
