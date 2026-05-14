import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';

interface SelectionChipProps {
  label: string;
  description: string;
  selected: boolean;
  onPress: () => void;
}

export function SelectionChip({ label, description, selected, onPress }: SelectionChipProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.container,
        selected ? styles.containerSelected : styles.containerIdle,
        pressed && styles.containerPressed,
      ]}
    >
      <View style={styles.textGroup}>
        <Text style={[styles.label, selected && styles.labelSelected]}>{label}</Text>
        <Text style={[styles.description, selected && styles.descriptionSelected]}>
          {description}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 20,
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  containerIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  containerSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  containerPressed: {
    opacity: 0.88,
  },
  textGroup: {
    gap: 6,
  },
  label: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  labelSelected: {
    color: colors.primary,
  },
  description: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  descriptionSelected: {
    color: colors.text,
  },
});
