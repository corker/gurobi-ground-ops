import { NewRun } from './NewRun'
import { RunPage } from './RunPage'
import { navigate, usePath } from './router'

function runId(path: string): string | null {
  const match = /^\/runs\/([^/]+)$/.exec(path)
  try {
    return match ? decodeURIComponent(match[1]) : null
  } catch {
    return null
  }
}

export default function App() {
  const path = usePath()
  const id = runId(path)
  return (
    <>
      <header>
        <a
          href="/"
          onClick={(event) => {
            // Let the browser open a new tab or window as usual.
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
            event.preventDefault()
            navigate('/')
          }}
        >
          ground-ops
        </a>
      </header>
      <main>
        {path === '/' ? (
          <NewRun />
        ) : id !== null ? (
          <RunPage key={id} id={id} />
        ) : (
          <p>There's no page at {path}.</p>
        )}
      </main>
    </>
  )
}
