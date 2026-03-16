// src/router/ProtectedRoute.jsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import Loader from '../components/common/Loader';

const ProtectedRoute = () => {
  // ১. চেক করা হচ্ছে লোকাল স্টোরেজে 'token' আছে কিনা
//   const token = localStorage.getItem('token');
    const token = localStorage.getItem('adminAccessToken');

  // ২. যদি টোকেন না থাকে (মানে লগইন করা নেই), তাকে লগইন পেজে পাঠাবে
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // ৩. যদি টোকেন থাকে, তাহলে সে যে পেজে যেতে চায় (ড্যাশবোর্ড) সেখানে যেতে দেবে
  return <Outlet />;
};

export default ProtectedRoute;


