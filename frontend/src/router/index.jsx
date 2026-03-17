// src/router/index.jsx
import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import AdminLayout from '../components/layout/AdminLayout';

import Dashboard         from '../pages/Dashboard';
import Users             from '../pages/Users';
import Security          from '../pages/Security';
import Wallet            from '../pages/Wallet';
import Tasks             from '../pages/Tasks';
import FraudDetection    from '../pages/FraudDetection';
import Settings          from '../pages/AdminPanel';
import KYC               from '../pages/KYC';
import Login from '../pages/Login';
import Signup from '../pages/Signup';
import ForgotPassword from '../pages/ForgotPassword';
import ResetPassword from '../pages/ResetPassword';
import PostbackDashboard from '../pages/PostbackDashboard';
import CMSPage           from '../pages/CMS';
import Backup            from '../pages/Backup';
import PaymentGateway    from '../pages/PaymentGateways';
import RateLimit         from '../pages/RateLimit';
import NotificationsPage from '../pages/Notifications';
import AdNetworks        from '../pages/AdNetworks';
import Offerwall         from '../pages/Offerwall';
import Alerts            from '../pages/Alerts';
import Support           from '../pages/Support';
import Localization      from '../pages/Localization';
import Referral          from '../pages/Referral';
import Cache             from '../pages/Cache';
import Analytics         from '../pages/Analytics';
import AuditLogs         from '../pages/AuditLogs';
import Engagement        from '../pages/Engagement';
import Loyalty           from '../pages/Loyalty';
import Promotions        from '../pages/Promotions';
import AdminSubmissions from '../pages/AdminSubmissions';
import AdminDisputes    from '../pages/AdminDisputes';
import AdminFinance     from '../pages/AdminFinance';
import AdminTools       from '../pages/AdminTools';
import ErrorBoundary     from '../components/common/ErrorBoundary';
import Profile           from '../pages/Profile';
import Messaging        from '../pages/Messaging';
import VersionControl   from '../pages/VersionControl';
import PayoutQueue      from '../pages/PayoutQueue';
import Inventory        from '../pages/Inventory';
import AutoMod          from '../pages/AutoMod';
import BehaviorAnalytics from '../pages/BehaviorAnalytics';
import Gamification     from '../pages/Gamification';
import Subscriptions    from '../pages/SubscriptionPage';


const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/signup', element: <Signup /> },
  { path: '/forgot-password', element: <ForgotPassword /> },
  { path: '/reset-password/:uid/:token', element: <ResetPassword /> },
  { path: '/postback', element: <ProtectedRoute/>, children: [{ index: true, element: <PostbackDashboard/> }] },
  {
    path: '/',
    element: <ProtectedRoute />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: 'rate-limit', element: <RateLimit /> },
      {
        element: <AdminLayout />,
        children: [
          { index: true,                  element: <Dashboard />        },
          { path: 'users',                element: <Users />            },
          { path: 'wallet',               element: <Wallet />           },
          { path: 'payment-gateways',     element: <PaymentGateway />   },
          { path: 'tasks',                element: <Tasks />            },
          { path: 'offerwall',            element: <Offerwall />        },
          { path: 'alerts',               element: <Alerts />           },
          { path: 'support',              element: <Support />          },
          { path: 'localization',         element: <Localization />     },
          { path: 'referral',             element: <Referral />         },
          { path: 'security',             element: <Security />         },
          { path: 'fraud-detection',      element: <FraudDetection />   },
          { path: 'kyc',                  element: <KYC />              },
          { path: 'audit-logs',           element: <AuditLogs />        },
          { path: 'cms',                  element: <CMSPage />          },
          { path: 'backup',               element: <Backup />           },
          { path: 'ad-networks',          element: <AdNetworks />       },
          { path: 'notifications',        element: <NotificationsPage />},
          { path: 'analytics',            element: <Analytics />        },
          { path: 'engagement',           element: <Engagement />       },
          { path: 'loyalty',              element: <Loyalty />          },
          { path: 'promotions',           element: <Promotions />       },
          { path: 'admin-submissions',    element: <AdminSubmissions />    },
          { path: 'admin-disputes',       element: <AdminDisputes />       },
          { path: 'admin-finance',        element: <AdminFinance />        },
          { path: 'admin-tools',          element: <AdminTools />          },
          { path: 'cache',                element: <Cache />            },
          { path: 'settings',             element: <Settings />         },
          { path: 'profile',              element: <Profile />          },
          { path: 'messaging',            element: <Messaging />        },
          { path: 'version-control',      element: <VersionControl />   },
          { path: 'payout-queue',         element: <PayoutQueue />      },
          { path: 'inventory',            element: <Inventory />        },
          { path: 'auto-mod',             element: <AutoMod />          },
          { path: 'behavior-analytics', element: <BehaviorAnalytics /> },
          { path: 'gamification',       element: <Gamification /> },
          { path: 'subscriptions',      element: <Subscriptions /> },
          { path: '*',                    element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
]);

export default router;
