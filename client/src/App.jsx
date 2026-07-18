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

const domainThemes = {
  'Mental Health': 'theme-mental-health',
  Legal: 'theme-legal',
  'Government Schemes': 'theme-government',
  Safety: 'theme-safety',
};

// Map URL ?domain= param values (from PWA manifest shortcuts) to domain names
const _DOMAIN_PARAM_MAP = {
  'mental-health': 'Mental Health',
  'legal': 'Legal',
  'schemes': 'Government Schemes',
  'safety': 'Safety',
};

function _initialDomain() {
  try {
    const param = new URLSearchParams(window.location.search).get('domain');
    return param ? (_DOMAIN_PARAM_MAP[param] ?? 'Mental Health') : 'Mental Health';
  } catch {
    return 'Mental Health';
  }
}

export default function App() {
  const [initialDomain] = useState(_initialDomain);
  const [theme, setTheme] = useState(domainThemes[initialDomain] ?? domainThemes['Mental Health']);
  const [authed, setAuthed] = useState(() => isAuthed());

  useEffect(() => subscribe(() => setAuthed(isAuthed())), []);

  useEffect(() => {
    document.body.className = `font-body antialiased min-h-screen ${theme}`;
  }, [theme]);

  const handleThemeChange = (domain) => {
    setTheme(domainThemes[domain] || 'theme-mental-health');
  };

  return (
    <ErrorBoundary>
      <TooltipProvider delayDuration={150}>
        <OfflineBanner />
        <div className="relative flex min-h-screen flex-col transition-colors duration-700">
          {authed ? (
            <>
              <AppHeader />
              <main className="flex-1 flex flex-col items-center px-4 sm:px-6 pt-2 pb-6">
                <div className="w-full max-w-4xl mx-auto">
                  <ChatAssistant onDomainChange={handleThemeChange} initialDomain={initialDomain} />
                </div>
              </main>
              <AppFooter />
            </>
          ) : (
            <LoginScreen />
          )}
          <Toaster />
        </div>
      </TooltipProvider>
    </ErrorBoundary>
  );
}
