import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NotificationPrompt from "./NotificationPrompt";
import TrialBanner from "./TrialBanner";

const NAV_ITEMS = [
  { to: "/post-job", label: "Post Job", icon: "＋" },
  { to: "/applications", label: "Applications", icon: "▤" },
  { to: "/approval-queue", label: "Approvals", icon: "✓" },
  { to: "/artifact-review", label: "Resumes/Docs", icon: "📄" },
  { to: "/candidate-submissions", label: "Profiles", icon: "◈" },
  { to: "/candidates", label: "Candidates", icon: "☰" },
  { to: "/job-check", label: "Quick Check", icon: "?" },
];

function NavLinkItem({ to, label, icon, mobile }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        mobile
          ? `flex flex-col items-center justify-center gap-1 flex-1 py-2 text-xs font-medium ${
              isActive ? "text-accent" : "text-ink/50"
            }`
          : `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              isActive ? "bg-accentSoft text-accent" : "text-ink/70 hover:bg-black/5"
            }`
      }
    >
      <span className={mobile ? "text-lg leading-none" : "text-base leading-none w-5 text-center"}>{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
}

export default function AppShell() {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <TrialBanner />
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:border-black/10 md:px-3 md:py-6">
        <div className="px-3 pb-6">
          <p className="text-sm font-semibold tracking-tight">AI Recruiter Agent</p>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.to} {...item} />
          ))}
        </nav>
        <button
          onClick={logout}
          className="mt-auto text-left px-4 py-2.5 rounded-lg text-sm font-medium text-ink/50 hover:bg-black/5"
        >
          Log out
        </button>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-black/10 sticky top-0 bg-paper z-10">
        <p className="text-sm font-semibold tracking-tight">AI Recruiter Agent</p>
        <button onClick={logout} className="text-xs font-medium text-ink/50">
          Log out
        </button>
      </header>

      <main className="flex-1 px-4 py-5 md:px-8 md:py-8 pb-20 md:pb-8 max-w-3xl w-full mx-auto">
        <Outlet />
      </main>

      <NotificationPrompt />

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 flex border-t border-black/10 bg-paper z-10">
        {NAV_ITEMS.map((item) => (
          <NavLinkItem key={item.to} {...item} mobile />
        ))}
      </nav>
    </div>
  );
}
