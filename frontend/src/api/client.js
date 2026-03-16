// src/api/client.js
import axios from 'axios';
import { setupRequestInterceptors } from './interceptors/request';
import { setupResponseInterceptors } from './interceptors/response';

const BASE_URL = 'http://127.0.0.1:8000/api/';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

setupRequestInterceptors(client);
setupResponseInterceptors(client);

export default client;