import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Footer } from '../components/Footer';

export const AppLayout: React.FC = () => {
  const location = useLocation();
  const isAskPolicyPage = location.pathname.startsWith('/ask');

  return (
    <div
      className={`flex flex-col ${
        isAskPolicyPage
          ? 'h-screen w-screen overflow-hidden bg-white'
          : 'min-h-screen bg-slate-50/50'
      }`}
    >
      <Navbar />

      <main
        className={`flex-1 w-full ${
          isAskPolicyPage
            ? 'h-[calc(100vh-4rem)] max-w-none p-0 m-0 flex flex-col overflow-hidden'
            : 'max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8'
        }`}
      >
        <Outlet />
      </main>

      {!isAskPolicyPage && <Footer />}
    </div>
  );
};
