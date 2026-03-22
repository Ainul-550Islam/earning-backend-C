// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { store } from './store/store';
import App from './App';
import './index.css';
import './design-system/styles/variables.css';
import './design-system/styles/cyberpunk.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')).render(
  
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
      <App />
    </Provider>
      </QueryClientProvider>
  
);// force redeploy Sun Mar 22 10:03:40 BST 2026
