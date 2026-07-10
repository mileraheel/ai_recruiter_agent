import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LOGIN_PATH } from "./config/roleRouting";
import AppShell from "./components/AppShell";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import AdminSignup from "./pages/AdminSignup";
import AcceptInvite from "./pages/AcceptInvite";
import ApprovalQueue from "./pages/ApprovalQueue";
import Candidates from "./pages/Candidates";
import JobCheck from "./pages/JobCheck";
import CandidateSubmissions from "./pages/CandidateSubmissions";
import CandidateSignup from "./pages/CandidateSignup";
import CandidateProfile from "./pages/CandidateProfile";
import MyApplications from "./pages/MyApplications";
import PostJob from "./pages/PostJob";
import Applications from "./pages/Applications";
import ArtifactReview from "./pages/ArtifactReview";
import SuperuserDashboard from "./pages/SuperuserDashboard";
import StaffDashboard from "./pages/StaffDashboard";
import AdminProfile from "./pages/AdminProfile";

function ProtectedRoute({ role, children }) {
  const { isAuthed, role: currentRole } = useAuth();
  if (!isAuthed) return <Navigate to={LOGIN_PATH} replace />;
  if (role && currentRole !== role) return <Navigate to={LOGIN_PATH} replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/signup" element={<AdminSignup />} />
      <Route path="/accept-invite" element={<AcceptInvite />} />
      {/* Old role-specific login pages are gone -- one unified /login now
          figures out the role from the credentials themselves. These
          redirects just keep any old bookmarks/links from dead-ending. */}
      <Route path="/superuser/login" element={<Navigate to={LOGIN_PATH} replace />} />
      <Route path="/staff/login" element={<Navigate to={LOGIN_PATH} replace />} />
      <Route path="/candidate/login" element={<Navigate to={LOGIN_PATH} replace />} />
      <Route
        path="/superuser/dashboard"
        element={
          <ProtectedRoute role="superuser">
            <SuperuserDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/staff/dashboard"
        element={
          <ProtectedRoute role="staff">
            <StaffDashboard />
          </ProtectedRoute>
        }
      />
      <Route path="/candidate/signup" element={<CandidateSignup />} />
      <Route
        path="/candidate/profile"
        element={
          <ProtectedRoute role="candidate">
            <CandidateProfile />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/applications"
        element={
          <ProtectedRoute role="candidate">
            <MyApplications />
          </ProtectedRoute>
        }
      />

      <Route
        element={
          <ProtectedRoute role="admin">
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/post-job" element={<PostJob />} />
        <Route path="/applications" element={<Applications />} />
        <Route path="/artifact-review" element={<ArtifactReview />} />
        <Route path="/approval-queue" element={<ApprovalQueue />} />
        <Route path="/candidates" element={<Candidates />} />
        <Route path="/job-check" element={<JobCheck />} />
        <Route path="/candidate-submissions" element={<CandidateSubmissions />} />
        <Route path="/admin/profile" element={<AdminProfile />} />
        <Route path="/" element={<Navigate to="/post-job" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/post-job" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
