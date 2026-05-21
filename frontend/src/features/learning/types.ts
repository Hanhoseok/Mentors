export interface LearningQuizOption {
  index: number;
  text: string;
}

export interface LearningQuiz {
  concept_id: number;
  concept_name: string;
  question: string;
  options: LearningQuizOption[];
}

export interface TierQuizCatalogResponse {
  tier: string;
  quizzes: LearningQuiz[];
}

export interface SubmitLearningQuizRequest {
  concept_id: number;
  answer_index: number;
}

export interface SubmitLearningQuizResponse {
  correct: boolean;
  explanation: string;
}
