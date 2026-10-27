import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppLayout } from './layouts/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AskPolicyPage } from './pages/AskPolicyPage';
import { PolicyExplorerPage } from './pages/PolicyExplorerPage';
import { ScenarioAnalyzerPage } from './pages/ScenarioAnalyzerPage';
import { ComparisonPage } from './pages/ComparisonPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';
import { ClaimRehearsalPage } from './pages/ClaimRehearsalPage';

// Route guard redirecting unauthenticated users to /login
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500 text-xs">
        <div className="flex flex-col items-center gap-2">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
          <span>Verifying CoverScope session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Route guard redirecting authenticated users away from /login
const PublicAuthRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicAuthRoute>
                <LoginPage />
              </PublicAuthRoute>
            }
          />

          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/ask" element={<AskPolicyPage />} />
            <Route path="/claim-rehearsal" element={<ClaimRehearsalPage />} />
            <Route path="/explorer" element={<PolicyExplorerPage />} />
            <Route path="/scenarios" element={<ScenarioAnalyzerPage />} />
            <Route path="/compare" element={<ComparisonPage />} />
            <Route path="/library" element={<DocumentLibraryPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
