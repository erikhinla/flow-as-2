import { useState } from 'react'
import { QueueMonitor } from './components/QueueMonitor'
import { PerformanceChart } from './components/PerformanceChart'
import { JobsTable } from './components/JobsTable'
import { SystemHealth } from './components/SystemHealth'
import { SkillsPanel } from './components/SkillsPanel'
import { FlowControl } from './components/FlowControl'
import { ClientOutcomes } from './components/ClientOutcomes'

type Tab = 'overview' | 'flow-control' | 'performance' | 'jobs' | 'skills' | 'settings'

function App() {
  const initialTab: Tab = window.location.pathname === '/flow-control' ? 'flow-control' : 'overview'
  const [activeTab, setActiveTab] = useState<Tab>(initialTab)

  const tabs = [
    { id: 'overview' as Tab, label: 'Clients' },
    { id: 'flow-control' as Tab, label: 'FLOW Control' },
    { id: 'performance' as Tab, label: 'Performance' },
    { id: 'jobs' as Tab, label: 'Jobs' },
    { id: 'skills' as Tab, label: 'Skills' },
  ]

  return (
    <div className="desk-shell">
      <header className="desk-header">
        <div className="desk-brand">
          <strong>BizBuilders desk</strong>
          <span>Infrastructure readiness reports</span>
        </div>
        <nav className="desk-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={activeTab === tab.id ? 'active' : ''}
              onClick={() => {
                setActiveTab(tab.id)
                window.history.replaceState(null, '', tab.id === 'flow-control' ? '/flow-control' : '/')
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <SystemHealth />
      </header>

      <main className="desk-main">
        {activeTab === 'overview' && <ClientOutcomes />}

        {activeTab === 'flow-control' && <FlowControl />}

        {activeTab === 'performance' && (
          <div className="space-y-8">
            <PerformanceChart expanded />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <QueueMonitor />
              <SkillsPanel />
            </div>
          </div>
        )}

        {activeTab === 'jobs' && <JobsTable />}

        {activeTab === 'skills' && <SkillsPanel expanded />}

        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Settings</h2>
            <p className="text-gray-600">Configuration options coming soon...</p>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
