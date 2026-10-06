import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import App from "./App";
import NewScreeningPage from "./pages/NewScreeningPage";
import ScreeningDetailsPage from "./pages/ScreeningDetailsPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<NewScreeningPage />} />
          <Route path="screenings/:screeningId" element={<ScreeningDetailsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
