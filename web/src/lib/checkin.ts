/** Pure check-in domain helpers — kept framework-free so they're trivially testable. */

export const SYMPTOMS = [
  { key: 'pain', label: 'Pain', question: 'How bad has your pain been today?' },
  { key: 'fatigue', label: 'Fatigue', question: 'How tired have you felt?' },
  { key: 'nausea', label: 'Nausea', question: 'Any nausea or vomiting?' },
  { key: 'appetite', label: 'Appetite', question: 'Any trouble eating or drinking?' },
  { key: 'mood', label: 'Mood', question: 'How low or worried have you felt?' },
] as const

export type SymptomKey = (typeof SYMPTOMS)[number]['key']

export const SCALE = [
  { value: 0, label: 'None' },
  { value: 1, label: 'Mild' },
  { value: 2, label: 'Moderate' },
  { value: 3, label: 'Severe' },
] as const

export type Scores = Record<SymptomKey, number | null>

export function emptyScores(): Scores {
  return { pain: null, fatigue: null, nausea: null, appetite: null, mood: null }
}

/** A check-in is submittable once every symptom has an answer. Free text is optional. */
export function isComplete(scores: Scores): boolean {
  return SYMPTOMS.every(({ key }) => scores[key] !== null)
}

export function missingSymptoms(scores: Scores): string[] {
  return SYMPTOMS.filter(({ key }) => scores[key] === null).map(({ label }) => label)
}

export function scaleLabel(value: number): string {
  return SCALE.find((s) => s.value === value)?.label ?? String(value)
}
