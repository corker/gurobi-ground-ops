import type { RunView, Schemas } from './api'
import { Conflicts } from './Conflicts'
import { Coverage } from './Coverage'
import { amount, percent } from './domain'
import { Schedule } from './Schedule'

const MEANING: Record<Schemas['Status'], string> = {
  optimal: 'Proven best: no schedule can beat it.',
  'limit reached':
    'Stopped by the work limit. This is the best found so far, if any; nothing can be better than the bound.',
  interrupted: 'Cancelled. This is the best found before the cancel, if any.',
  infeasible: 'No schedule can satisfy every rule.',
}

export function ResultView({ run }: { run: RunView }) {
  if (run.state === 'failed' || run.result === null) {
    return <p role="alert">The run failed: {run.error ?? 'no result'}</p>
  }
  const { result, instance } = run
  const unit = 'tasks' in instance ? 'min overtime' : 'paid half-hours'
  return (
    <section aria-label="Result">
      <p role="status">
        <strong>{result.status}</strong>: {MEANING[result.status]}
      </p>
      {result.status !== 'infeasible' && (
        <dl>
          <dt>Objective</dt>
          <dd>
            {result.objective === null
              ? 'no solution found'
              : `${amount(result.objective)} ${unit}`}
          </dd>
          <dt>Bound</dt>
          <dd>{result.bound === null ? 'none yet' : `${amount(result.bound)} ${unit}`}</dd>
          <dt>Gap</dt>
          <dd>{percent(result.gap)}</dd>
        </dl>
      )}
      {'tasks' in instance ? (
        result.status === 'infeasible' ? (
          <Conflicts instance={instance} iis={result.iis ?? []} />
        ) : (
          Object.keys(result.solution).length > 0 && (
            <Schedule instance={instance} solution={result.solution} />
          )
        )
      ) : (
        Object.keys(result.solution).length > 0 && (
          <Coverage instance={instance} staffing={result.solution} />
        )
      )}
    </section>
  )
}
