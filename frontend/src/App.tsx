import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import AthleteProfile from './pages/AthleteProfile'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/athlete/:id" element={<AthleteProfile />} />
    </Routes>
  )
}

export default App
