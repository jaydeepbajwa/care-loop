export type Severity = 'low' | 'moderate' | 'high' | 'urgent'

export interface EligibilityAnswers {
  cancer_diagnosis: boolean
  age_18_or_over: boolean
  insurance: 'medicare_advantage' | 'medicaid' | 'commercial' | 'none' | 'other'
}

export interface EnrollmentState {
  token: string
  status: 'in_progress' | 'ineligible' | 'enrolled'
  current_step: string
  first_name: string | null
  last_name: string | null
  phone: string | null
  email: string | null
  contact_preference: 'sms' | 'email' | 'phone' | null
  eligibility_answers: EligibilityAnswers | null
  consented: boolean
}

export interface CheckIn {
  id: string
  pain: number
  fatigue: number
  nausea: number
  appetite: number
  mood: number
  free_text: string | null
  flagged: boolean
  flag_reason: string | null
  created_at: string
}

export interface Suggestion {
  id: string
  check_in_id: string
  severity: Severity
  suggested_action: string
  rationale: string
  source: 'llm' | 'rules'
  model: string | null
  status: 'pending' | 'accepted' | 'overridden'
  decided_by: string | null
  decision_note: string | null
  final_severity: string | null
  final_action: string | null
  created_at: string
  decided_at: string | null
}

export interface QueueItem {
  member_name: string
  member_id: string
  check_in: CheckIn
  suggestion: Suggestion
}

export interface MemberSummary {
  id: string
  name: string
  status: string
  enrolled_at: string | null
  last_check_in_at: string | null
  open_flags: number
}

export interface FunnelReport {
  started: number
  eligibility_passed: number
  eligibility_failed: number
  consented: number
  enrolled: number
}
