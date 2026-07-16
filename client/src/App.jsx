import { useEffect, useState, lazy, Suspense } from 'react';
import ChatAssistant from '@/components/chat-assistant';
import { AppHeader } from '@/components/app-header';
import { AppFooter } from '@/components/app-footer';
import { LoginScreen } from '@/components/login';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ErrorBoundary } from '@/components/error-boundary';
import { OfflineBanner } from '@/components/offline-banner';
import { isAuthed, subscribe } from '@/lib/auth';

const AdminPanel = lazy(() => import('@/components/admin/AdminPanel'));

const domainThemes = {
  'Mental Health': 'theme-mental-health',
  Legal: 'theme-legal',
  'Government Schemes': 'theme-government',
  Safety: 'theme-safety',
};

export default function App() {
  const [theme, setTheme] = useState(domainThemes['Mental Health']);
  const [authed, setAuthed] = useState(() => isAuthed());
  const [adminMode, setAdminMode] = useState(false);

  useEffect(() => subscribe(() => setAuthed(isAuthed())), []);

  useEffect(() => {
    document.body.className = `font-body antialiased min-h-screen ${adminMode ? 'theme-admin' : theme}`;
  }, [theme, adminMode]);

  const handleThemeChange = (domain) => {
    setTheme(domainThemes[domain] || 'theme-mental-health');
  };

  const enterAdmin = () => setAdminMode(true);
  const exitAdmin  = () => setAdminMode(false);

  return (
    <ErrorBoundary>
      <TooltipProvider delayDuration={150}>
        <OfflineBanner />
        {authed && adminMode ? (
          <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center">
              <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" aria-label="Loading admin panel" />
            </div>
          }>
            <AdminPanel onExit={exitAdmin} />
          </Suspense>
        ) : (
          <div className="relative flex min-h-screen flex-col transition-colors duration-700">
            {authed ? (
              <>
                <AppHeader onAdminClick={enterAdmin} />
                <main className="flex-1 flex flex-col items-center px-4 sm:px-6 pt-2 pb-6">
                  <div className="w-full max-w-4xl mx-auto">
                    <ChatAssistant onDomainChange={handleThemeChange} />
                  </div>
                </main>
                <AppFooter />
              </>
            ) : (
              <LoginScreen />
            )}
            <Toaster />
          </div>
        )}
      </TooltipProvider>
    </ErrorBoundary>
  );
}
