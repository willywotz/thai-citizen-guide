import { Toaster } from "@/shared/components/ui/toaster";
import { Toaster as Sonner } from "@/shared/components/ui/sonner";
import { TooltipProvider } from "@/shared/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/shared/components/ThemeProvider";
import { AuthProvider } from "@/features/auth/useAuth";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { AppLayout } from "@/shared/components/layout/AppLayout";
import ChatPage from "@/features/chat/ChatPage";
import DashboardPage from "@/features/dashboard/DashboardPage";
import ExecutivePage from "@/features/executive/ExecutivePage";
import HealthPage from "@/features/health/HealthPage";
import HeatmapPage from "@/features/heatmap/HeatmapPage";
import AgenciesPage from "@/features/agencies/AgenciesPage";
import AgencyDetailPage from "@/features/agencies/detail/AgencyDetailPage";
import AgencyWizardPage from "@/features/agencies/wizard/AgencyWizardPage";
import HistoryPage from "@/features/history/HistoryPage";
import ArchitecturePage from "@/features/architecture/ArchitecturePage";
import ConnectionLogsPage from "@/features/connection-logs/ConnectionLogsPage";
import PublicPortal from "@/features/public/PublicPortal";
import LoginPage from "@/features/auth/LoginPage";
import SignupPage from "@/features/auth/SignupPage";
import ForgotPasswordPage from "@/features/auth/ForgotPasswordPage";
import ResetPasswordPage from "@/features/auth/ResetPasswordPage";
import ApiKeysPage from "@/features/api-keys/ApiKeysPage";
import SettingsPage from "@/features/settings/SettingsPage";
import UsersPage from "@/features/users/UsersPage";
import NotFound from "@/shared/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<PublicPortal />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/executive" element={<ExecutivePage />} />
                <Route path="/health" element={<HealthPage />} />
                <Route path="/heatmap" element={<HeatmapPage />} />
                <Route path="/agencies" element={<AgenciesPage />} />
                <Route path="/agencies/new" element={<AgencyWizardPage />} />
                <Route path="/agencies/:id/setup" element={<AgencyWizardPage />} />
                <Route path="/agencies/:id" element={<AgencyDetailPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/connection-logs" element={<ConnectionLogsPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />
                <Route path="/api-keys" element={<ApiKeysPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/users" element={<ProtectedRoute requireAdmin><UsersPage /></ProtectedRoute>} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
