import { useState } from 'react'
import { BarChart3, Brain, ClipboardCheck, Gauge, Workflow } from 'lucide-react'
import { QueueMonitor } from './components/QueueMonitor'
import { PerformanceChart } from './components/PerformanceChart'
import { JobsTable } from './components/JobsTable'
import { SystemHealth } from './components/SystemHealth'
import { SkillsPanel } from './components/SkillsPanel'
import { FlowControl } from './components/FlowControl'

type Tab = 'overview' | 'flow-control' | 'performance' | 'jobs' | 'skills'

const pathForTab: Record<Tab, string> = {
  'flow-control': '/',
  overview: '/signal',
  jobs: '/jobs',
  performance: '/performance',
  skills: '/learning',
}

function tabForPath(pathname: string): Tab {
  if (pathname === '/signal') return 'overview'
  if (pathname === '/jobs') return 'jobs'
  if (pathname === '/performance') return 'performance'
  if (pathname === '/learning') return 'skills'
  return 'flow-control'
}

function App() {
  const initialTab = tabForPath(window.location.pathname)
  const [activeTab, setActiveTab] = useState<Tab>(initialTab)

  const tabs = [
    { id: 'flow-control' as Tab, label: 'Work', icon: Workflow },
    { id: 'overview' as Tab, label: 'Signal', icon: Gauge },
    { id: 'jobs' as Tab, label: 'Proof', icon: ClipboardCheck },
    { id: 'performance' as Tab, label: 'Performance', icon: BarChart3 },
    { id: 'skills' as Tab, label: 'Learning', icon: Brain },
  ]

  function selectTab(tab: Tab) {
    setActiveTab(tab)
    window.history.replaceState(null, '', pathForTab[tab])
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to work</a>
      <header className="command-rail">
        <div className="mx-auto max-w-[1500px] px-5 sm:px-8 lg:px-10">
          <div className="flex min-h-[5.25rem] flex-col justify-center gap-3 py-3 lg:flex-row lg:items-center lg:justify-between lg:py-0">
            <div className="flex min-w-0 flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:gap-8">
              <div className="shrink-0">
                <p className="font-flow-mono text-[0.62rem] uppercase tracking-[0.24em] text-flow-accent">FLOW / control surface</p>
                <p className="mt-1 text-sm font-medium tracking-tight text-white">Clear work. Visible proof.</p>
              </div>
              <nav aria-label="Dashboard sections" className="flow-scrollbar -mx-2 flex min-w-0 max-w-full items-center overflow-x-auto px-2">
                  {tabs.map((tab) => {
                    const Icon = tab.icon
                    return (
                      <button
                        key={tab.id}
                        onClick={() => selectTab(tab.id)}
                        className="command-tab"
                        aria-current={activeTab === tab.id ? 'page' : undefined}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        <span>{tab.label}</span>
                      </button>
                    )
                  })}
              </nav>
            </div>
            <div className="shrink-0"><SystemHealth /></div>
          </div>
        </div>
      </header>

      <main id="main-content">
        {activeTab === 'flow-control' && <FlowControl />}

        {activeTab === 'overview' && (
          <div className="mx-auto max-w-[1500px] space-y-7 px-5 pb-16 pt-8 sm:px-8 lg:px-10 lg:pt-10">
            <section className="signal-panel grid gap-8 rounded-2xl px-6 py-7 md:grid-cols-[1.2fr_0.8fr] md:px-8 md:py-9">
              <div>
                <p className="font-flow-mono text-[0.68rem] uppercase tracking-[0.2em] text-flow-accent">Operating signal</p>
                <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-[1.02] tracking-[-0.045em] sm:text-5xl">Ready is different from busy.</h1>
              </div>
              <div className="self-end border-l border-white/15 pl-6 text-sm leading-6 text-white/65">
                This view separates healthy capacity, work in motion, review holds, and completed proof. An empty queue means ready for the next clear brief—not failure.
              </div>
            </section>
            <div className="grid grid-cols-1 gap-7 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <QueueMonitor />
              </div>
              <div>
                <PerformanceChart />
              </div>
            </div>
            <JobsTable limit={10} />
          </div>
        )}

        {activeTab === 'performance' && (
          <div className="mx-auto max-w-[1500px] space-y-8 px-5 py-8 sm:px-8 lg:px-10">
            <PerformanceChart expanded />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <QueueMonitor />
              <SkillsPanel />
            </div>
          </div>
        )}

        {activeTab === 'jobs' && <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-8 lg:px-10"><JobsTable /></div>}

        {activeTab === 'skills' && <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-8 lg:px-10"><SkillsPanel expanded /></div>}
      </main>
    </div>
  )
}

export default App
