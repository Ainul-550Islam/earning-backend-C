// src/components/layout/AdminLayout.jsx
import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

const AdminLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [adminUser, setAdminUser] = useState(null);
  // ✅ NEW: sidebar width state
  const [sidebarWidth, setSidebarWidth] = useState(210);

  const fetchUser = () => {
    const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
    fetch('/api/auth/profile/my_profile/', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const d = data.data || data;
        setAdminUser({
          name:   d.username || d.full_name || d.name || 'Admin',
          email:  d.email || '',
          role:   d.role || d.user_type || 'Admin',
          avatar: d.avatar ? (d.avatar.startsWith('http') ? d.avatar : `http://127.0.0.1:8000${d.avatar}`) : null,
        });
      }).catch(() => {});
  };

  useEffect(() => { fetchUser(); }, []);
  useEffect(() => {
    window.addEventListener('profile-updated', fetchUser);
    return () => window.removeEventListener('profile-updated', fetchUser);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('adminAccessToken');
    localStorage.removeItem('adminRefreshToken');
    localStorage.removeItem('auth_token');
    navigate('/login');
  };

  return (
    <div style={{
      minHeight: '100vh', background: '#03010c', color: '#eae0ff',
      fontFamily: "'Exo 2','Rajdhani',sans-serif",
      position: 'relative', display: 'flex',
    }}>

      {/* Stars */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
        backgroundImage: `
          radial-gradient(1px 1px at 4% 8%, rgba(255,255,255,.9) 0%,transparent 100%),
          radial-gradient(1px 1px at 11% 82%, rgba(255,255,255,.7) 0%,transparent 100%),
          radial-gradient(1.5px 1.5px at 17% 38%, rgba(180,150,255,.8) 0%,transparent 100%),
          radial-gradient(2px 2px at 44% 12%, rgba(255,215,0,.6) 0%,transparent 100%),
          radial-gradient(1px 1px at 50% 88%, rgba(255,255,255,.8) 0%,transparent 100%),
          radial-gradient(1.5px 1.5px at 70% 22%, rgba(0,243,255,.7) 0%,transparent 100%),
          radial-gradient(1px 1px at 76% 73%, rgba(255,255,255,.9) 0%,transparent 100%),
          radial-gradient(2px 2px at 82% 44%, rgba(255,45,120,.5) 0%,transparent 100%)
        `,
        animation: 'twinkle 7s ease-in-out infinite alternate',
      }} />
      <div style={{
        position: 'fixed', bottom: -60, left: 0, right: 0, height: 500,
        background: `
          radial-gradient(ellipse at 20% 100%, rgba(180,0,255,.16) 0%,transparent 55%),
          radial-gradient(ellipse at 80% 100%, rgba(255,0,100,.10) 0%,transparent 55%)
        `,
        pointerEvents: 'none', zIndex: 0, filter: 'blur(30px)',
      }} />
      <style>{`@keyframes twinkle { 0%{opacity:.5} 100%{opacity:1} }`}</style>

      {/* ✅ Sidebar — onWidthChange দিয়ে width জানাবে */}
      <div style={{ position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50 }}>
        <Sidebar user={adminUser} onWidthChange={setSidebarWidth} />
      </div>

      {/* ✅ Main — sidebarWidth অনুযায়ী margin, smooth transition */}
      <div style={{
        marginLeft: sidebarWidth,
        transition: 'margin-left .32s cubic-bezier(.4,0,.2,1)',
        flex: 1, minHeight: '100vh',
        display: 'flex', flexDirection: 'column',
        position: 'relative', zIndex: 1,
      }}>
        <div style={{ position: 'sticky', top: 0, zIndex: 40 }}>
          <Header onLogout={handleLogout} user={adminUser} />
        </div>
        <main style={{ flex: 1, overflowY: 'auto', overflowX: 'visible', background: 'transparent' }}>
          <Outlet />
        </main>
      </div>

    </div>
  );
};

export default AdminLayout;



// // src/components/layout/AdminLayout.jsx
// import React, { useState, useEffect } from 'react';
// import { Outlet, useNavigate, useLocation } from 'react-router-dom';
// import Sidebar from './Sidebar';
// import Header from './Header';

// const AdminLayout = () => {
//   const navigate  = useNavigate();
//   const location  = useLocation();

//   const [adminUser, setAdminUser] = useState(null);

//   useEffect(() => {
//     const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
//     fetch('/api/auth/profile/my_profile/', { headers: { 'Authorization': `Bearer ${token}` } })
//       .then(r => r.ok ? r.json() : null)
//       .then(data => {
//         const d = data.data || data;
//         setAdminUser({
//           name: d.username || d.full_name || d.name || 'Admin',
//           email: d.email || '',
//           role: d.role || d.user_type || 'Admin',
//           avatar: d.avatar ? (d.avatar.startsWith('http') ? d.avatar : `http://127.0.0.1:8000${d.avatar}`) : null,
//         });
//       }).catch(() => {});
//   }, []);

//   useEffect(() => {
//     const handler = () => {
//       const token = localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || "";
//       fetch("/api/auth/profile/my_profile/", { headers: { "Authorization": "Bearer " + token } })
//         .then(r => r.ok ? r.json() : null)
//         .then(data => {
//           const d = data.data || data;
//           setAdminUser({
//             name: d.username || d.full_name || d.name || "Admin",
//             email: d.email || "",
//             role: d.role || d.user_type || "Admin",
//             avatar: d.avatar ? (d.avatar.startsWith("http") ? d.avatar : "http://127.0.0.1:8000" + d.avatar) : null,
//           });
//         }).catch(() => {});
//     };
//     window.addEventListener("profile-updated", handler);
//     return () => window.removeEventListener("profile-updated", handler);
//   }, []);

//   useEffect(() => {
//     const refresh = () => {
//       const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
//       fetch('/api/auth/profile/my_profile/', { headers: { 'Authorization': 'Bearer ' + token } })
//         .then(r => r.ok ? r.json() : null)
//         .then(data => {
//           const d = data.data || data;
//           setAdminUser({
//             name: d.username || d.full_name || 'Admin',
//             email: d.email || '',
//             role: d.role || d.user_type || 'Admin',
//             avatar: d.avatar ? (d.avatar.startsWith('http') ? d.avatar : 'http://127.0.0.1:8000' + d.avatar) : null,
//           });
//         }).catch(() => {});
//     };
//     window.addEventListener('profile-updated', refresh);
//     return () => window.removeEventListener('profile-updated', refresh);
//   }, []);

//   const rawPath = location.pathname.replace('/', '') || 'dashboard';

//   // ── Logout ──
//   const handleLogout = () => {
//     localStorage.removeItem('adminAccessToken');
//     localStorage.removeItem('adminRefreshToken');
//     localStorage.removeItem('auth_token');
//     navigate('/login');
//   };

//   return (
//     <div style={{
//       minHeight: '100vh',
//       background: '#03010c',
//       color: '#eae0ff',
//       fontFamily: "'Exo 2','Rajdhani',sans-serif",
//       position: 'relative',
//       display: 'flex',
//     }}>

//       {/* Stars */}
//       <div style={{
//         position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
//         backgroundImage: `
//           radial-gradient(1px 1px at 4% 8%, rgba(255,255,255,.9) 0%,transparent 100%),
//           radial-gradient(1px 1px at 11% 82%, rgba(255,255,255,.7) 0%,transparent 100%),
//           radial-gradient(1.5px 1.5px at 17% 38%, rgba(180,150,255,.8) 0%,transparent 100%),
//           radial-gradient(2px 2px at 44% 12%, rgba(255,215,0,.6) 0%,transparent 100%),
//           radial-gradient(1px 1px at 50% 88%, rgba(255,255,255,.8) 0%,transparent 100%),
//           radial-gradient(1.5px 1.5px at 70% 22%, rgba(0,243,255,.7) 0%,transparent 100%),
//           radial-gradient(1px 1px at 76% 73%, rgba(255,255,255,.9) 0%,transparent 100%),
//           radial-gradient(2px 2px at 82% 44%, rgba(255,45,120,.5) 0%,transparent 100%)
//         `,
//         animation: 'twinkle 7s ease-in-out infinite alternate',
//       }} />

//       {/* Bottom nebula */}
//       <div style={{
//         position: 'fixed', bottom: -60, left: 0, right: 0, height: 500,
//         background: `
//           radial-gradient(ellipse at 20% 100%, rgba(180,0,255,.16) 0%,transparent 55%),
//           radial-gradient(ellipse at 80% 100%, rgba(255,0,100,.10) 0%,transparent 55%)
//         `,
//         pointerEvents: 'none', zIndex: 0, filter: 'blur(30px)',
//       }} />

//       <style>{`@keyframes twinkle { 0%{opacity:.5} 100%{opacity:1} }`}</style>

//       {/* Sidebar */}
//       <div style={{ position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50 }}>
//         <Sidebar user={adminUser} />
//       </div>

//       {/* Main */}
//       <div style={{
//         marginLeft: 210, flex: 1, minHeight: '100vh',
//         display: 'flex', flexDirection: 'column',
//         position: 'relative', zIndex: 1,
//       }}>
//         <div style={{ position: 'sticky', top: 0, zIndex: 40 }}>
//           <Header onLogout={handleLogout} user={adminUser} />
//         </div>
//         <main style={{ flex: 1, overflowY: 'auto', overflowX: 'visible', background: 'transparent' }}>
//           <Outlet />
//         </main>
//       </div>
//     </div>
//   );
// };

// export default AdminLayout;
