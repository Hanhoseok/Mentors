import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import type { AppStackParamList } from '@/navigation/types';

/**
 * 검색·검색결과·뉴스상세 화면 우측 상단에 공통으로 들어가는 아이콘 바.
 * 🔔 알림 · 📌 스크랩(→ ScrapScreen) · 👤 프로필(→ Settings).
 *
 * `showProfile=false`로 프로필 아이콘을 숨길 수 있다(상세 화면 등).
 */
export function TopIconBar({ showProfile = true }: { showProfile?: boolean }) {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();

  return (
    <View style={styles.iconRow}>
      <Pressable
        onPress={() => Alert.alert('알림', '새로운 알림이 없습니다.')}
        style={styles.iconBtn}
      >
        <Text style={styles.iconText}>🔔</Text>
      </Pressable>
      <Pressable onPress={() => navigation.navigate('Scrap')} style={styles.iconBtn}>
        <Text style={styles.iconText}>📌</Text>
      </Pressable>
      {showProfile ? (
        <Pressable onPress={() => navigation.navigate('Settings')} style={styles.iconBtn}>
          <Text style={styles.iconText}>👤</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  iconRow: {
    flexDirection: 'row',
    gap: 8,
  },
  iconBtn: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  iconText: {
    fontSize: 18,
  },
});
