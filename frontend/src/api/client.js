// src/api/client.js
import axios from 'axios';
import { setupRequestInterceptors } from './interceptors/request';
import { setupResponseInterceptors } from './interceptors/response';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

setupRequestInterceptors(client);
setupResponseInterceptors(client);

export default client;