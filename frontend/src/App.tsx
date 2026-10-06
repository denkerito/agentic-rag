import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Home from './components/Home'
import Layout from './components/Layout'
import VistaIndagine from './components/VistaIndagine'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="indagini/:id" element={<VistaIndagine />} />
          <Route path="*" element={<Home />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
