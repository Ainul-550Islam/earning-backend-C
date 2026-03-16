// src/utils/constants.js
import {
  LayoutDashboard,
  Users,
  Wallet,
  ClipboardList,
  ShieldCheck,
  ScanSearch,
  BarChart3,
  Gift,
  HeartPulse,
  LayoutGrid,
  Bell,
  UserCheck,
  AlertTriangle,
  FileText,
  Headphones,
  Settings,
  Wifi,
  Crown,
  CreditCard,
  ScrollText,
  Database,
  Zap,
  Gauge,
  Globe,
} from 'lucide-react';

export const MENU_ITEMS = [
  {
    title: 'Main',
    items: [
      {
        name: 'Dashboard',
        path: '/',
        icon: LayoutDashboard,
        module: 'adminPanel', // Maps to adminPanel app
      },
    ],
  },
  {
    title: 'Management',
    items: [
      {
        name: 'Users',
        path: '/users',
        icon: Users,
        module: 'users',
      },
      {
        name: 'Wallet',
        path: '/wallet',
        icon: Wallet,
        module: 'wallet',
      },
      {
        name: 'Tasks',
        path: '/tasks',
        icon: ClipboardList,
        module: 'tasks',
      },
      {
        name: 'Offerwall',
        path: '/offerwall',
        icon: LayoutGrid,
        module: 'offerwall',
      },
      {
        name: 'Referrals',
        path: '/referral',
        icon: Gift,
        module: 'referral',
      },
    ],
  },
  {
    title: 'Security & Compliance',
    items: [
      {
        name: 'Security Logs',
        path: '/security',
        icon: ShieldCheck,
        module: 'security',
      },
      {
        name: 'Fraud Detection',
        path: '/fraud-detection',
        icon: ScanSearch,
        module: 'fraudDetection',
      },
      {
        name: 'KYC Verification',
        path: '/kyc',
        icon: UserCheck,
        module: 'kyc',
      },
      {
        name: 'Audit Logs',
        path: '/audit-logs',
        icon: ScrollText,
        module: 'auditLogs',
      },
    ],
  },
  {
    title: 'Analytics & Growth',
    items: [
      {
        name: 'Analytics',
        path: '/analytics',
        icon: BarChart3,
        module: 'analytics',
      },
      {
        name: 'Engagement',
        path: '/engagement',
        icon: HeartPulse,
        module: 'engagement',
      },
      {
        name: 'DJ Loyalty',
        path: '/loyalty',
        icon: Crown,
        module: 'djoyalty',
      },
    ],
  },
  {
    title: 'Finance & Gateways',
    items: [
      {
        name: 'Payment Gateways',
        path: '/payment-gateways',
        icon: CreditCard,
        module: 'paymentGateways',
      },
    ],
  },
  {
    title: 'System & Config',
    items: [
      {
        name: 'Notifications',
        path: '/notifications',
        icon: Bell,
        module: 'notifications',
      },
      {
        name: 'Alerts Center',
        path: '/alerts',
        icon: AlertTriangle,
        module: 'alerts',
      },
      {
        name: 'CMS',
        path: '/cms',
        icon: FileText,
        module: 'cms',
      },
      {
        name: 'Support',
        path: '/support',
        icon: Headphones,
        module: 'support',
      },
      {
        name: 'Ad Networks',
        path: '/ad-networks',
        icon: Wifi,
        module: 'adNetworks',
      },
      {
        name: 'Localization',
        path: '/localization',
        icon: Globe,
        module: 'localization',
      },
      {
        name: 'Rate Limits',
        path: '/rate-limit',
        icon: Gauge,
        module: 'rateLimit',
      },
      {
        name: 'Cache Manager',
        path: '/cache',
        icon: Zap,
        module: 'cache',
      },
      {
        name: 'Backups',
        path: '/backup',
        icon: Database,
        module: 'backup',
      },
      {
        name: 'Admin Settings',
        path: '/settings',
        icon: Settings,
        module: 'adminPanel',
      },
    ],
  },
];

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';