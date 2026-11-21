import { useEffect, useState } from 'react'
import { cancelRun, describe, followRun, getRun, type Progress, type RunView } from './api'
import { amount, grafanaUrl, percent } from './domain'
import { ProgressChart } from './ProgressChart'
import { ResultView } from './ResultView'

export function RunPage({ id }: { id: string }) {
  const [run, setRun] = useState<RunView | null>(null)
  const [samples, setSamples] = useState<Progress[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let stop = () => {}
    const fail = (failure: unknown) => active && setError(describe(failure))
    const refresh = () => {
      void getRun(id).then((final) => active && setRun(final), fail)
    }
    getRun(id).then((view) => {
      if (!active) return
      setRun(view)
      if (view.state !== 'running') return
      stop = followRun(id, {
        progress: (sample) => setSamples((previous) => [...previous, sample]),
        done: refresh,
        lost: refresh,
      })
    }, fail)
    return () => {
      active = false
      stop()
    }
  }, [id])

  if (error) return <p role="alert">{error}</p>
  if (!run) return <p>Loading run {id}…</p>
  return (
    <>
      <h1>
        Run {run.id}: {run.model === 'assignment' ? 'Model 1' : 'Model 2'}
      </h1>
      {run.exported && (
        <p>
          <a href={grafanaUrl(run)} target="_blank" rel="noreferrer">
            Open this run in Grafana
          </a>
        </p>
      )}
      {run.state === 'running' ? <Live id={run.id} samples={samples} /> : <ResultView run={run} />}
    </>
  )
}

function Live({ id, samples }: { id: string; samples: Progress[] }) {
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const latest = samples.at(-1)
  return (
    <section aria-label="Live progress">
      <p>Solving…</p>
      {latest && (
        <dl>
          <dt>Incumbent</dt>
          <dd>{amount(latest.incumbent)}</dd>
          <dt>Bound</dt>
          <dd>{amount(latest.bound)}</dd>
          <dt>Gap</dt>
          <dd>{percent(latest.gap)}</dd>
          <dt>Nodes</dt>
          <dd>{latest.nodes}</dd>
          <dt>Elapsed</dt>
          <dd>{latest.elapsed.toFixed(1)} s</dd>
        </dl>
      )}
      <ProgressChart samples={samples} />
      <button
        type="button"
        disabled={cancelling}
        onClick={() => {
          setCancelling(true)
          setCancelError(null)
          void cancelRun(id).catch((failure: unknown) => {
            setCancelling(false)
            setCancelError(describe(failure))
          })
        }}
      >
        {cancelling ? 'Cancelling…' : 'Cancel'}
      </button>
      {cancelError && <p role="alert">Cancel failed: {cancelError}</p>}
    </section>
  )
}
