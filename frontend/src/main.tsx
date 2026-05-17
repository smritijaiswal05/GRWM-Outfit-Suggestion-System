import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
const { fetch: originalFetch } = window;

window.fetch = async (...args) => {
  let [resource, config] = args;

  // Ensure config and headers exist
  config = config || {};
  const headers = new Headers(config.headers || {});
  
  // Inject the bypass header
  headers.set('ngrok-skip-browser-warning', 'true');
  
  config.headers = headers;

  return originalFetch(resource, config);
};
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
