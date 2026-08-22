import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import AthleteProfile from './pages/AthleteProfile'
import AppShell from './components/AppShell'
import { ThemeProvider } from './lib/theme'

function App() {
  return (
    <ThemeProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/athlete/:id" element={<AthleteProfile />} />
        </Routes>
      </AppShell>
    </ThemeProvider>
  )
}

export default App
