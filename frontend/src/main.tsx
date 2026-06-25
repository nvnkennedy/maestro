import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { ProjectProvider } from './context/ProjectContext';
import { ToastProvider } from './components/common/Toast';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <ProjectProvider>
          <App />
        </ProjectProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
