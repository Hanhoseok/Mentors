import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { colors } from '@/constants/colors';
import { getHeaderActionIconName, type AppIconName, type HeaderActionKey } from '@/ui/iconTokens';

export function AppIcon({
  color = colors.text,
  name,
  size = 20,
  style,
}: {
  color?: string;
  name: AppIconName;
  size?: number;
  style?: StyleProp<TextStyle>;
}) {
  return <MaterialCommunityIcons color={color} name={name} size={size} style={style} />;
}

export function IconLabel({
  color = colors.text,
  icon,
  iconColor,
  iconSize = 16,
  label,
  style,
  textStyle,
}: {
  color?: string;
  icon: AppIconName;
  iconColor?: string;
  iconSize?: number;
  label: string;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}) {
  return (
    <View style={[styles.labelRow, style]}>
      <AppIcon color={iconColor ?? color} name={icon} size={iconSize} />
      <Text style={[styles.labelText, { color }, textStyle]}>{label}</Text>
    </View>
  );
}

export function HeaderActionButton({
  action,
  onPress,
  showUnreadDot = false,
  style,
}: {
  action: HeaderActionKey;
  onPress: () => void;
  showUnreadDot?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.headerButton, style, pressed && styles.pressed]}>
      <AppIcon color={colors.text} name={getHeaderActionIconName(action)} size={20} />
      {showUnreadDot ? <View style={styles.unreadDot} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  labelRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
  },
  labelText: {
    fontSize: 14,
    fontWeight: '700',
  },
  headerButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    height: 40,
    justifyContent: 'center',
    position: 'relative',
    width: 40,
  },
  unreadDot: {
    backgroundColor: '#E63946',
    borderColor: colors.surface,
    borderRadius: 6,
    borderWidth: 1.5,
    height: 10,
    position: 'absolute',
    right: 6,
    top: 6,
    width: 10,
  },
  pressed: {
    opacity: 0.8,
  },
});
