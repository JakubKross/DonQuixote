import { Link, NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="app-title">
          DonQuixote
        </Link>
        <span className="app-subtitle">wstępny screening OZE</span>
        <nav className="app-nav">
          <NavLink to="/" end>
            Analizy
          </NavLink>
          <NavLink to="/new">Nowy screening</NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        Wynik jest materiałem pomocniczym do dalszej analizy. Nie jest wiążącą
        opinią prawną, nie gwarantuje możliwości realizacji inwestycji i
        wymaga sprawdzenia aktualności danych oraz oceny eksperta.
      </footer>
    </div>
  );
}
