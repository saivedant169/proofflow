export type LogTone = 'seed' | 'change' | 'refresh' | 'verify' | 'reset' | 'error'
export interface LogLine { kind: 'ran' | 'reused' | 'note' | 'fail' | 'pass'; text: string }
export interface LogEntry { id: number; title: string; tone: LogTone; lines: LogLine[] }

export default function Activity({ entries }: { entries: LogEntry[] }) {
  return (
    <section className="demo-activity" aria-labelledby="demo-activity-title">
      <h3 className="demo-panel-title" id="demo-activity-title">Activity</h3>
      <p className="demo-fine">Newest first. Every “ran” line is a real tool execution in this replay.</p>
      <ol className="demo-log scroll-thin" tabIndex={0} aria-label="Activity log, newest first">
        {entries.map(entry => (
          <li key={entry.id} className={`demo-log-entry is-${entry.tone}`}>
            <p className="demo-log-title">{entry.title}</p>
            {entry.lines.length > 0 && (
              <ul className="demo-log-lines">
                {entry.lines.map((line, index) => (
                  <li key={index} className={`is-${line.kind}`}>
                    <span className="demo-log-glyph" aria-hidden />
                    {line.text}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
