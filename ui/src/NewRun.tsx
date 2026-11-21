import { useState, type FormEvent } from 'react'
import { describe, startRun, type RunRequest } from './api'
import { navigate } from './router'

function optionalNumber(value: FormDataEntryValue | null): number | null {
  return value === null || value === '' ? null : Number(value)
}

export function NewRun() {
  const [model, setModel] = useState<RunRequest['model']>('assignment')
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const seed = optionalNumber(form.get('seed'))
    const request: RunRequest = {
      model,
      ...(seed !== null && { seed }),
      expose_search: form.get('expose_search') === 'on',
      work_limit: optionalNumber(form.get('work_limit')),
      ...(model === 'assignment' && {
        tasks: Number(form.get('tasks')),
        handlers: optionalNumber(form.get('handlers')),
      }),
    }
    setStarting(true)
    setError(null)
    try {
      navigate(`/runs/${encodeURIComponent((await startRun(request)).id)}`)
    } catch (failure) {
      setError(describe(failure))
      setStarting(false)
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <h1>New run</h1>
      <fieldset>
        <legend>Model</legend>
        <label>
          <input
            type="radio"
            name="model"
            checked={model === 'assignment'}
            onChange={() => setModel('assignment')}
          />
          Model 1: who does which task
        </label>
        <label>
          <input
            type="radio"
            name="model"
            checked={model === 'coverage'}
            onChange={() => setModel('coverage')}
          />
          Model 2: how many people on each shift
        </label>
      </fieldset>
      {model === 'assignment' && (
        <>
          <label>
            Tasks (even) <input name="tasks" type="number" min={2} step={2} defaultValue={30} />
          </label>
          <label>
            Handlers (empty: one more than the most tasks that overlap){' '}
            <input name="handlers" type="number" min={0} />
          </label>
        </>
      )}
      <label>
        Seed <input name="seed" type="number" defaultValue={1} />
      </label>
      <label>
        <input name="expose_search" type="checkbox" /> Expose the search (Presolve=0, Cuts=0)
      </label>
      <label>
        Work limit (empty: none) <input name="work_limit" type="number" min={0} step="any" />
      </label>
      <button type="submit" disabled={starting}>
        Start
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
