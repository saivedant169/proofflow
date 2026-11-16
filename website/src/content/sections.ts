/** Page order. The lineage rail and nav read from this list. */
export const SECTIONS = [
  { id: 'top', label: 'Overview', nav: false },
  { id: 'problem', label: 'The problem', nav: false },
  { id: 'how', label: 'How it works', nav: true },
  { id: 'demo', label: 'Demo', nav: true },
  { id: 'results', label: 'Results', nav: true },
  { id: 'architecture', label: 'Architecture', nav: true },
  { id: 'evaluation', label: 'Evaluation', nav: true },
  { id: 'try', label: 'Try it', nav: false },
] as const

export type SectionId = (typeof SECTIONS)[number]['id']
export const SECTION_IDS: readonly string[] = SECTIONS.map(s => s.id)
