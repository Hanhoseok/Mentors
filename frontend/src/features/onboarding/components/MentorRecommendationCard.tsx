import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
import type { MentorRecommendation } from '../types';

interface MentorRecommendationCardProps {
  mentor: MentorRecommendation;
  selected: boolean;
  onPress: () => void;
}

export function MentorRecommendationCard({
  mentor,
  selected,
  onPress,
}: MentorRecommendationCardProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.container,
        {
          borderColor: selected ? mentor.accentColor : colors.border,
          backgroundColor: selected ? `${mentor.accentColor}14` : colors.surface,
        },
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.headerRow}>
        <View style={styles.headerText}>
          <Text style={styles.name}>{mentor.name}</Text>
          <Text style={[styles.title, { color: mentor.accentColor }]}>{mentor.title}</Text>
        </View>
        <View style={[styles.scoreBadge, { backgroundColor: `${mentor.accentColor}20` }]}>
          <Text style={[styles.scoreText, { color: mentor.accentColor }]}>
            추천도 {mentor.score}
          </Text>
        </View>
      </View>

      <Text style={styles.oneLiner}>{mentor.oneLiner}</Text>
      <Text style={styles.idealFor}>어울리는 사용자: {mentor.idealFor}</Text>

      <View style={styles.reasonList}>
        {mentor.reasons.map((reason) => (
          <Text key={reason} style={styles.reasonItem}>
            • {reason}
          </Text>
        ))}
      </View>

      <View style={styles.tagRow}>
        {mentor.strengths.map((strength) => (
          <View key={strength} style={styles.tag}>
            <Text style={styles.tagText}>{strength}</Text>
          </View>
        ))}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 24,
    borderWidth: 1,
    padding: 18,
    gap: 12,
  },
  pressed: {
    opacity: 0.9,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  headerText: {
    flex: 1,
    gap: 4,
  },
  name: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
  },
  scoreBadge: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  scoreText: {
    fontSize: 12,
    fontWeight: '800',
  },
  oneLiner: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  idealFor: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  reasonList: {
    gap: 6,
  },
  reasonItem: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: colors.surface,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  tagText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
});
