// src/store/store.js
import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import userReducer from './slices/userSlice'; // Assuming userSlice exists or will be added

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    user: userReducer,
    // Add other reducers here (e.g., wallet: walletReducer)
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
});

export default store;