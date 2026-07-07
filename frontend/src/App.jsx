import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppShell from "./components/AppShell";
import Login from "./pages/Login";
import AdminSignup from "./pages/AdminSignup";
import AcceptInvite from "./pages/AcceptInvite";
import ApprovalQueue from "./pages/ApprovalQueue";
import Candidates from "./pages/Candidates";
import JobCheck from "./pages/JobCheck";
import CandidateSubmissions from "./pages/CandidateSubmissions";
import CandidateLogin from "./pages/CandidateLogin";
import CandidateSignup from "./pages/CandidateSignup";
import CandidateProfile from "./pages/CandidateProfile";
import MyApplications from "./pages/MyApplications";
import PostJob from "./pages/PostJob";
import Applications from "./pages/Applications";
import ArtifactReview from "./pages/ArtifactReview";
import SuperuserLogin from "./pages/SuperuserLogin";
import SuperuserDashboard from "./pages/SuperuserDashboard";
import StaffLogin from "./pages/StaffLogin";
import StaffDashboard from "./pages/StaffDashboard";

function loginPathFor(role) {
  if (role === "candidate") return "/candidate/login";
  if (role === "superuser") return "/superuser/login";
  if (role === "staff") return "/staff/login";
  return "/login";
}

function ProtectedRoute({ role, children }) {
  const { isAuthed, role: currentRole } = useAuth();
  if (!isAuthed) return <Navigate to={loginPathFor(role)} replace />;
  if (role && currentRole !== role) return <Navigate to={loginPathFor(role)} replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<AdminSignup />} />
      <Route path="/accept-invite" element={<AcceptInvite />} />
      <Route path="/superuser/login" element={<SuperuserLogin />} />
      <Route
        path="/superuser/dashboard"
        element={
          <ProtectedRoute role="superuser">
            <SuperuserDashboard />
          </ProtectedRoute>
        }
      />
      <Route path="/staff/login" element={<StaffLogin />} />
      <Route
        path="/staff/dashboard"
        element={
          <ProtectedRoute role="staff">
            <StaffDashboard />
          </ProtectedRoute>
        }
      />
      <Route path="/candidate/login" element={<CandidateLogin />} />
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
