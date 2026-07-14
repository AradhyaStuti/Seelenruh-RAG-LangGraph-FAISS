import { useEffect, useState } from 'react';
import ChatAssistant from '@/components/chat-assistant';
import { AppHeader } from '@/components/app-header';
import { AppFooter } from '@/components/app-footer';
import { LoginScreen } from '@/components/login';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ErrorBoundary } from '@/components/error-boundary';
import { OfflineBanner } from '@/components/offline-banner';
import { isAuthed, subscribe } from '@/lib/auth';
import AdminPanel from '@/components/admin/AdminPanel';

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
          <AdminPanel onExit={exitAdmin} />
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
