// import { useState, useEffect } from 'react';
// import useAuth from './hooks/useAuth'
// import { getDashboardStats } from './api/endpoints/analytics';
// import { TrendingUp, TrendingDown, DollarSign, MousePointerClick, Target, Users, Copy, Check, Bell, Menu, X, ChevronRight, Award, Clock, Zap } from 'lucide-react';

// export default function EarningProDashboard() {
//   const [stats, setStats] = useState({
//     balance: 125.50,
//     todayEarnings: 125.43,
//     todayChange: 15,
//     clicks: 847,
//     clicksChange: 8,
//     conversions: 42,
//     conversionsChange: -2,
//     activeUsers: 3245,
//     activeChange: 4.8,
//     referrals: 15,
//     referralEarnings: 125.50
//   });

//   const [activities, setActivities] = useState([
//     { id: 1, type: 'Ad Click', amount: 0.05, status: 'completed', time: '2 min ago' },
//     { id: 2, type: 'Survey', amount: 1.50, status: 'pending', time: '15 min ago' },
//     { id: 3, type: 'App Install', amount: 2.00, status: 'completed', time: '1 hour ago' },
//     { id: 4, type: 'Referral', amount: 5.00, status: 'completed', time: '3 hours ago' }
//   ]);

//   const [offers, setOffers] = useState([
//     { id: 1, type: 'Survey', amount: 1.50, time: '10 min', icon: '📝', category: 'Quick' },
//     { id: 2, type: 'App Install', amount: 2.00, time: '5 min', icon: '⬇️', category: 'Featured' },
//     { id: 3, type: 'Watch Ad', amount: 0.10, time: '30 sec', icon: '📱', category: 'Instant' },
//     { id: 4, type: 'Game Trial', amount: 3.50, time: '20 min', icon: '🎮', category: 'Hot' },
//     { id: 5, type: 'Sign Up', amount: 1.25, time: '3 min', icon: '✍️', category: 'Quick' }
//   ]);

//   const [copied, setCopied] = useState(false);
//   const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
//   const [selectedTab, setSelectedTab] = useState('overview');
//   const referralCode = 'EARN123';
//   const { logout } = useAuth()

//   const copyReferralCode = () => {
//     navigator.clipboard.writeText(referralCode);
//     setCopied(true);
//     setTimeout(() => setCopied(false), 2000);
//   };

//   const chartData = [
//     { day: 'Mon', value: 85 },
//     { day: 'Tue', value: 92 },
//     { day: 'Wed', value: 78 },
//     { day: 'Thu', value: 105 },
//     { day: 'Fri', value: 125 },
//     { day: 'Sat', value: 110 },
//     { day: 'Sun', value: 95 }
//   ];

//   const maxValue = Math.max(...chartData.map(d => d.value));

//   useEffect(() => {
//     let mounted = true;
//     (async () => {
//       try {
//         const data = await getDashboardStats();
//         if (!mounted || !data) return;

//         // Map API response into local `stats` shape, with fallbacks
//         setStats(prev => ({
//           balance: data.balance ?? data.total_balance ?? prev.balance,
//           todayEarnings: data.today_earnings ?? data.todayEarnings ?? prev.todayEarnings,
//           todayChange: data.today_change ?? data.todayChange ?? prev.todayChange,
//           clicks: data.clicks ?? data.total_clicks ?? prev.clicks,
//           clicksChange: data.clicks_change ?? prev.clicksChange ?? prev.clicksChange,
//           conversions: data.conversions ?? data.total_conversions ?? prev.conversions,
//           conversionsChange: data.conversions_change ?? prev.conversionsChange ?? prev.conversionsChange,
//           activeUsers: data.active_users ?? data.activeUsers ?? prev.activeUsers,
//           activeChange: data.active_change ?? prev.activeChange ?? prev.activeChange,
//           referrals: data.referrals ?? prev.referrals,
//           referralEarnings: data.referral_earnings ?? prev.referralEarnings
//         }));
//       } catch (e) {
//         // keep using defaults — log for debugging
//         // eslint-disable-next-line no-console
//         console.warn('Could not load dashboard stats:', e.message || e);
//       }
//     })();
//     return () => { mounted = false; };
//   }, []);

//   return (
//     <div className="min-h-screen bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950 text-white overflow-x-hidden">
//       {/* Animated Background */}
//       <div className="fixed inset-0 overflow-hidden pointer-events-none">
//         <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse"></div>
//         <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
//       </div>

//       {/* Header */}
//       <header className="relative z-10 border-b border-white/10 bg-slate-900/50 backdrop-blur-xl">
//         <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
//           <div className="flex items-center gap-3">
//             <button onClick={() => window.dispatchEvent(new Event('sidebar:toggle'))} className="md:hidden p-2 rounded-lg bg-white/5 mr-2">
//               <Menu className="w-5 h-5" />
//             </button>
//             <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-2 rounded-xl rotate-12 hover:rotate-0 transition-transform duration-300">
//               <Zap className="w-6 h-6 -rotate-12 hover:rotate-0 transition-transform duration-300" />
//             </div>
//             <h1 className="text-2xl font-black tracking-tight bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
//               EARNING PRO
//             </h1>
//           </div>

//           <div className="hidden md:flex items-center gap-6">
//             <button onClick={() => { window.history.pushState({}, '', '/users'); window.dispatchEvent(new PopStateEvent('popstate')) }} className="px-3 py-2 bg-white/5 rounded-lg">Users</button>
//             <div className="flex items-center gap-2 bg-gradient-to-r from-purple-500/20 to-pink-500/20 px-4 py-2 rounded-full border border-purple-500/30">
//               <DollarSign className="w-5 h-5 text-green-400" />
//               <span className="font-bold text-lg">${parseFloat(stats.balance || 0).toFixed(2)}</span>
//             </div>
//             <button className="p-2 hover:bg-white/10 rounded-lg transition-colors relative">
//               <Bell className="w-5 h-5" />
//               <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
//             </button>
//             <button onClick={() => { logout(); window.history.pushState({}, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate')) }} className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center font-bold hover:scale-110 transition-transform">
//               Logout
//             </button>
//           </div>

//           <button 
//             className="md:hidden p-2 hover:bg-white/10 rounded-lg transition-colors"
//             onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
//           >
//             {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
//           </button>
//         </div>

//         {/* Mobile Menu */}
//         {mobileMenuOpen && (
//           <div className="md:hidden absolute top-full left-0 right-0 bg-slate-900/95 backdrop-blur-xl border-b border-white/10 p-4 space-y-3">
//             <div className="flex items-center gap-2 bg-gradient-to-r from-purple-500/20 to-pink-500/20 px-4 py-3 rounded-xl border border-purple-500/30">
//               <DollarSign className="w-5 h-5 text-green-400" />
//               <span className="font-bold text-lg">Balance: ${parseFloat(stats.balance || 0).toFixed(2)}</span>
//             </div>
//             <button className="w-full py-3 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
//               Profile
//             </button>
//             <button onClick={() => { logout(); window.history.pushState({}, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate')) }} className="w-full py-3 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
//               Logout
//             </button>
//           </div>
//         )}
//       </header>

//       <main className="relative z-10 max-w-7xl mx-auto px-4 py-8">
//         {/* Stats Grid */}
//         <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
//           <StatCard
//             title="TODAY"
//             value={`$${stats.todayEarnings}`}
//             change={stats.todayChange}
//             icon={<DollarSign className="w-5 h-5" />}
//             color="from-green-500 to-emerald-500"
//           />
//           <StatCard
//             title="CLICKS"
//             value={stats.clicks.toLocaleString()}
//             change={stats.clicksChange}
//             icon={<MousePointerClick className="w-5 h-5" />}
//             color="from-blue-500 to-cyan-500"
//           />
//           <StatCard
//             title="CONVERSIONS"
//             value={stats.conversions}
//             change={stats.conversionsChange}
//             icon={<Target className="w-5 h-5" />}
//             color="from-purple-500 to-pink-500"
//           />
//           <StatCard
//             title="ACTIVE"
//             value={stats.activeUsers.toLocaleString()}
//             change={stats.activeChange}
//             icon={<Users className="w-5 h-5" />}
//             color="from-orange-500 to-red-500"
//           />
//         </div>

//         {/* Earnings Chart */}
//         <div className="mb-8 bg-slate-900/50 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-purple-500/30 transition-colors">
//           <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
//             <div className="w-1 h-6 bg-gradient-to-b from-purple-500 to-pink-500 rounded-full"></div>
//             Earnings Overview (Last 7 Days)
//           </h2>
//           <div className="space-y-4">
//             {chartData.map((item, index) => (
//               <div key={item.day} className="flex items-center gap-4">
//                 <span className="text-sm font-medium text-white/60 w-12">{item.day}</span>
//                 <div className="flex-1 h-10 bg-slate-800/50 rounded-lg overflow-hidden relative group">
//                   <div 
//                     className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg transition-all duration-1000 ease-out flex items-center justify-end px-3"
//                     style={{ 
//                       width: `${(item.value / maxValue) * 100}%`,
//                       animationDelay: `${index * 100}ms`
//                     }}
//                   >
//                     <span className="text-sm font-bold text-white opacity-0 group-hover:opacity-100 transition-opacity">
//                       ${item.value}
//                     </span>
//                   </div>
//                 </div>
//               </div>
//             ))}
//           </div>
//         </div>

//         {/* Activity & Offers Grid */}
//         <div className="grid md:grid-cols-2 gap-6 mb-8">
//           {/* Recent Activity */}
//           <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-blue-500/30 transition-colors">
//             <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
//               <Clock className="w-5 h-5 text-blue-400" />
//               Recent Activity
//             </h2>
//             <div className="space-y-3">
//               {activities.map((activity) => (
//                 <div 
//                   key={activity.id}
//                   className="flex items-center justify-between p-3 bg-slate-800/50 rounded-xl hover:bg-slate-800/70 transition-all group cursor-pointer"
//                 >
//                   <div className="flex items-center gap-3">
//                     <div className={`w-2 h-2 rounded-full ${activity.status === 'completed' ? 'bg-green-400' : 'bg-yellow-400'} animate-pulse`}></div>
//                     <div>
//                       <p className="font-medium group-hover:text-purple-400 transition-colors">{activity.type}</p>
//                       <p className="text-xs text-white/50">{activity.time}</p>
//                     </div>
//                   </div>
//                   <div className="text-right">
//                     <p className="font-bold text-green-400">+${parseFloat(activity.amount || 0).toFixed(2)}</p>
//                     <p className="text-xs text-white/50">{activity.status === 'completed' ? '✓' : '⏳'}</p>
//                   </div>
//                 </div>
//               ))}
//             </div>
//           </div>

//           {/* Available Offers */}
//           <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-pink-500/30 transition-colors">
//             <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
//               <Award className="w-5 h-5 text-pink-400" />
//               Available Offers
//             </h2>
//             <div className="space-y-3">
//               {offers.slice(0, 4).map((offer) => (
//                 <button 
//                   key={offer.id}
//                   className="w-full flex items-center justify-between p-3 bg-slate-800/50 rounded-xl hover:bg-gradient-to-r hover:from-purple-500/20 hover:to-pink-500/20 transition-all group border border-transparent hover:border-purple-500/50"
//                 >
//                   <div className="flex items-center gap-3">
//                     <span className="text-2xl">{offer.icon}</span>
//                     <div className="text-left">
//                       <p className="font-medium group-hover:text-purple-400 transition-colors">{offer.type}</p>
//                       <p className="text-xs text-white/50">{offer.time} • {offer.category}</p>
//                     </div>
//                   </div>
//                   <div className="flex items-center gap-2">
//                     <span className="font-bold text-green-400">+${parseFloat(offer.amount || 0).toFixed(2)}</span>
//                     <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-purple-400 transition-colors" />
//                   </div>
//                 </button>
//               ))}
//             </div>
//           </div>
//         </div>

//         {/* Referral Program */}
//         <div className="bg-gradient-to-br from-purple-900/50 to-pink-900/50 backdrop-blur-xl rounded-2xl p-6 border border-purple-500/30">
//           <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
//             <div>
//               <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
//                 <Users className="w-5 h-5 text-purple-400" />
//                 Referral Program
//               </h2>
//               <p className="text-white/60 text-sm">Invite friends and earn 20% of their earnings forever!</p>
//             </div>
//             <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
//               <div className="text-center sm:text-right">
//                 <p className="text-sm text-white/60">Total Referred</p>
//                 <p className="text-2xl font-bold text-purple-400">{stats.referrals}</p>
//               </div>
//               <div className="text-center sm:text-right">
//                 <p className="text-sm text-white/60">Earnings</p>
//                 <p className="text-2xl font-bold text-green-400">${parseFloat(stats.referralEarnings || 0).toFixed(2)}</p>
//               </div>
//             </div>
//           </div>
//           <div className="mt-4 flex items-center gap-2 bg-slate-900/50 p-4 rounded-xl border border-white/10">
//             <span className="text-sm text-white/60 font-medium">Your Code:</span>
//             <code className="flex-1 font-mono font-bold text-lg text-purple-400">{referralCode}</code>
//             <button 
//               onClick={copyReferralCode}
//               className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg font-bold hover:scale-105 transition-transform flex items-center gap-2"
//             >
//               {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
//               {copied ? 'Copied!' : 'Copy'}
//             </button>
//           </div>
//         </div>
//       </main>

//       {/* Inline styled-jsx block removed to avoid non-boolean `jsx` attribute warnings.
//           Font import moved to src/index.css and Tailwind directives are applied there. */}
//     </div>
//   );
// }

// function StatCard({ title, value, change, icon, color }) {
//   const isPositive = change >= 0;
  
//   return (
//     <div className={`bg-slate-900/50 backdrop-blur-xl rounded-2xl p-4 border border-white/10 hover:border-purple-500/30 transition-all hover:scale-105 hover:shadow-2xl hover:shadow-purple-500/20 cursor-pointer group`}>
//       <div className="flex items-center justify-between mb-2">
//         <span className="text-xs font-bold text-white/60 tracking-wider">{title}</span>
//         <div className={`bg-gradient-to-br ${color} p-2 rounded-lg group-hover:scale-110 transition-transform`}>
//           {icon}
//         </div>
//       </div>
//       <div className="flex items-end justify-between">
//         <p className="text-2xl font-black">{value}</p>
//         <div className={`flex items-center gap-1 text-sm font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
//           {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
//           <span>{Math.abs(change)}%</span>
//         </div>
//       </div>
//     </div>
//   );
// }