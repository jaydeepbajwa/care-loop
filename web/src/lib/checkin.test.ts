import { describe, expect, it } from 'vitest'

import { emptyScores, isComplete, missingSymptoms, scaleLabel } from './checkin'

describe('check-in completion', () => {
  it('starts incomplete with every symptom listed as missing', () => {
    const scores = emptyScores()
    expect(isComplete(scores)).toBe(false)
    expect(missingSymptoms(scores)).toEqual(['Pain', 'Fatigue', 'Nausea', 'Appetite', 'Mood'])
  })

  it('a zero ("None") is a real answer, not a missing one', () => {
    const scores = { ...emptyScores(), pain: 0 }
    expect(missingSymptoms(scores)).not.toContain('Pain')
  })

  it('is complete only when all five symptoms are answered', () => {
    const scores = { pain: 0, fatigue: 1, nausea: 0, appetite: 2, mood: 0 }
    expect(isComplete(scores)).toBe(true)
    expect(isComplete({ ...scores, mood: null })).toBe(false)
  })
})

describe('scale labels', () => {
  it('maps the 0-3 scale to patient-friendly words', () => {
    expect([0, 1, 2, 3].map(scaleLabel)).toEqual(['None', 'Mild', 'Moderate', 'Severe'])
  })
})
