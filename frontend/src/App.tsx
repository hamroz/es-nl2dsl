import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { 
  BeakerIcon, 
  ChartBarIcon, 
  ShieldCheckIcon, 
  EyeSlashIcon,
  CogIcon,
  ServerIcon 
} from '@heroicons/react/24/outline';

// Import page components (to be created)
import QueryGenerator from './pages/QueryGenerator';
import EvaluationDashboard from './pages/EvaluationDashboard';
import SecurityTesting from './pages/SecurityTesting';
import PrivacyAnalysis from './pages/PrivacyAnalysis';
import SystemAdmin from './pages/SystemAdmin';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const navigation = [
  { name: 'Query Generator', href: '/', icon: BeakerIcon },
  { name: 'Evaluation', href: '/evaluation', icon: ChartBarIcon },
  { name: 'Security Testing', href: '/security', icon: ShieldCheckIcon },
  { name: 'Privacy Analysis', href: '/privacy', icon: EyeSlashIcon },
  { name: 'System Admin', href: '/admin', icon: CogIcon },
];

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-gray-100">
          {/* Navigation Sidebar */}
          <div className="fixed inset-y-0 left-0 z-50 w-64 bg-gray-900">
            <div className="flex flex-col h-full">
              {/* Logo */}
              <div className="flex items-center h-16 px-4 bg-gray-800">
                <ServerIcon className="w-8 h-8 text-blue-400" />
                <span className="ml-2 text-lg font-semibold text-white">
                  ES-NL2DSL
                </span>
              </div>

              {/* Navigation Links */}
              <nav className="flex-1 px-2 py-4 space-y-2">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    to={item.href}
                    className="flex items-center px-2 py-2 text-sm font-medium text-gray-300 rounded-md hover:bg-gray-700 hover:text-white group"
                  >
                    <item.icon className="w-5 h-5 mr-3 text-gray-400 group-hover:text-gray-300" />
                    {item.name}
                  </Link>
                ))}
              </nav>
            </div>
          </div>

          {/* Main Content */}
          <div className="pl-64">
            <main className="py-6">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <Routes>
                  <Route path="/" element={<QueryGenerator />} />
                  <Route path="/evaluation" element={<EvaluationDashboard />} />
                  <Route path="/security" element={<SecurityTesting />} />
                  <Route path="/privacy" element={<PrivacyAnalysis />} />
                  <Route path="/admin" element={<SystemAdmin />} />
                </Routes>
              </div>
            </main>
          </div>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
