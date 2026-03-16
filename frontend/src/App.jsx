// src/App.jsx
import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import router from './router';
import { ThemeProvider } from './context/ThemeContext';
import './styles/GlobalLayout.css';

function App() {
  return (
    <ThemeProvider>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'rgba(10,10,26,0.9)',
            color: '#fff',
            border: '1px solid rgba(0,243,255,0.2)',
          }
        }}
      />
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

export default App;


