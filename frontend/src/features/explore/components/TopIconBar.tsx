import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { AppStackParamList } from '@/navigation/types';
import { useInAppNotificationStore } from '@/store/inAppNotificationStore';
import { HeaderActionButton } from '@/components/AppIcon';

/**
 * 검색·검색결과·뉴스상세 화면 우측 상단에 공통으로 들어가는 아이콘 바.
 * 알림(→ NotificationsScreen) · 스크랩(→ ScrapScreen) · 프로필(→ Settings).
 *
 * - `showProfile=false`로 프로필 아이콘을 숨길 수 있다(상세 화면 등).
 * - `showScrap=false`로 스크랩 아이콘을 숨긴다. ScrapScreen 자기 자신처럼
 *   이미 스크랩 화면일 때 같은 화면으로 navigate되는 것을 막는다.
 */
export function TopIconBar({
  showProfile = true,
  showScrap = true,
}: {
  showProfile?: boolean;
  showScrap?: boolean;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const unreadCount = useInAppNotificationStore((s) => s.unreadCount);

  return (
    <View style={styles.iconRow}>
      <HeaderActionButton
        action="notifications"
        onPress={() => navigation.navigate('Notifications')}
        showUnreadDot={unreadCount > 0}
      />
      {showScrap ? (
        <HeaderActionButton action="scrap" onPress={() => navigation.navigate('Scrap')} />
      ) : null}
      {showProfile ? (
        <HeaderActionButton action="settings" onPress={() => navigation.navigate('Settings')} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  iconRow: {
    flexDirection: 'row',
    gap: 8,
  },
});
