import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import VistaIndagine from './components/VistaIndagine'

function Benvenuto() {
  return (
    <section className="benvenuto">
      <h1>Indaga i dati economici dell'azienda</h1>
      <p>
        Scrivi una domanda nella barra a sinistra. L'agente interroga il database e i documenti,
        mostra ogni passo e restituisce una risposta con numeri e fonti che puoi aprire e
        controllare.
      </p>
      <p className="muted">
        I numeri vengono sempre da query SQL in sola lettura. Se una causa non è documentata,
        l'agente lo dice.
      </p>
    </section>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Benvenuto />} />
          <Route path="indagini/:id" element={<VistaIndagine />} />
          <Route path="*" element={<Benvenuto />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
