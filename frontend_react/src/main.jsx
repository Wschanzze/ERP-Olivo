import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// Montar la isla React en el elemento contenedor provisto por Django
const container = document.getElementById('react-dashboard-island');
if (container) {
  const apiUrl = container.dataset.apiUrl || '/api/v1/dashboard/kpis/';
  const root = ReactDOM.createRoot(container);
  root.render(
    <React.StrictMode>
      <App apiUrl={apiUrl} />
    </React.StrictMode>
  );
}
