import './style.css'
import { loadSettings, applyFontScale, openSettings } from './components/Settings.js'
import { openAbout } from './components/About.js'
import { renderGraphPage } from './pages/GraphPage.js'
import { renderBuildPage } from './pages/BuildPage.js'
import { renderDriftPage } from './pages/DriftPage.js'
import { parseHash, navigate, replaceRoute, startRouter } from './router.js'

applyFontScale(loadSettings().fontScale)

const app = document.getElementById('app')
app.innerHTML = `
  <div class="gide">
    <div class="gide__topbar">
      <h1>Graph IDE</h1>
      <nav class="gide__nav" id="nav">
        <a data-page="graph">Graph</a>
        <a data-page="build">Build</a>
        <a data-page="drift">Drift</a>
      </nav>
      <span class="gide__status" id="status"></span>
      <div class="gide__topbar-spacer"></div>
      <a class="gide__settings-link" id="settings-link">⚙ Settings</a>
      <a class="gide__settings-link" id="about-link">ℹ About</a>
    </div>
    <div id="page-root"></div>
  </div>
`

const statusEl = document.getElementById('status')
const pageRoot = document.getElementById('page-root')
const nav = document.getElementById('nav')

function setStatus(text) {
  statusEl.textContent = text
}

let currentGraph = null

// --- global build job — lives here, not in BuildPage, so it survives
// navigating to another page (and keeps updating the topbar status even
// while a different page is showing) ---------------------------------------
const buildListeners = new Set()
let buildState = { status: 'idle', root: null, returncode: null, output: '' }

function setBuildState(next) {
  buildState = { ...buildState, ...next }
  buildListeners.forEach(fn => fn(buildState))
  if (buildState.status === 'running') setStatus(`building ${buildState.root}…`)
  else if (buildState.status === 'done') setStatus(`build ok — ${buildState.root}`)
  else if (buildState.status === 'error') setStatus(`build failed (exit ${buildState.returncode}) — ${buildState.root}`)
}

let buildPollTimer = null
function stopBuildPoll() {
  if (buildPollTimer) {
    clearInterval(buildPollTimer)
    buildPollTimer = null
  }
}
async function pollBuildStatus() {
  try {
    const res = await fetch('/api/build/status')
    const data = await res.json()
    setBuildState(data)
    if (data.status !== 'running') stopBuildPoll()
  } catch (err) {
    stopBuildPoll()
    setStatus(`error polling build status: ${err.message}`)
  }
}
async function startBuild(root, outputDir) {
  if (!root || buildState.status === 'running') return
  setBuildState({ status: 'running', root, returncode: null, output: '' })
  try {
    const res = await fetch('/api/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root, output_dir: outputDir || '' }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || res.statusText)
    stopBuildPoll()
    buildPollTimer = setInterval(pollBuildStatus, 2000)
    pollBuildStatus()
  } catch (err) {
    setBuildState({ status: 'error', returncode: null, output: `error starting build: ${err.message}` })
  }
}
async function cancelBuild() {
  try {
    await fetch('/api/build/cancel', { method: 'POST' })
  } catch {
    // next poll reflects whatever actually happened
  }
}
const buildCtx = {
  get state() { return buildState },
  subscribe: fn => buildListeners.add(fn),
  unsubscribe: fn => buildListeners.delete(fn),
  start: startBuild,
  cancel: cancelBuild,
}

// Resume polling if a build was already in flight before this page loaded
// (e.g. a refresh mid-build).
fetch('/api/build/status')
  .then(res => res.json())
  .then(data => {
    setBuildState(data)
    if (data.status === 'running') buildPollTimer = setInterval(pollBuildStatus, 2000)
  })
  .catch(() => {})

// --- routing ----------------------------------------------------------------
const pages = {
  graph: renderGraphPage,
  build: renderBuildPage,
  drift: renderDriftPage,
}

let unmountCurrent = null

function renderRoute(route) {
  if (unmountCurrent) {
    unmountCurrent()
    unmountCurrent = null
  }
  pageRoot.innerHTML = ''
  ;[...nav.children].forEach(a => {
    const active = a.dataset.page === route.page
    a.classList.toggle('active', active)
    a.href = `#/${a.dataset.page}`
  })

  const renderPage = pages[route.page] || pages.graph
  const ctx = {
    params: route.params,
    navigate,
    replaceRoute,
    setStatus,
    build: buildCtx,
    onGraphChange: graph => {
      currentGraph = graph
    },
  }
  unmountCurrent = renderPage(pageRoot, ctx) || null
}

startRouter(renderRoute)

document.getElementById('settings-link').addEventListener('click', () => openSettings(() => renderRoute(parseHash())))
document.getElementById('about-link').addEventListener('click', () => openAbout(currentGraph))
