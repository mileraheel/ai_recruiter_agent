import { NavLink, Outlet } from "react-router-dom";
import { APP_NAME } from "../config/appInfo";
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
  { to: "/admin/profile", label: "Profile", icon: "⚙" },
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
              isActive ? "bg-accentSoft text-accent" : "text-ink/70 hover:bg-ink/5"
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
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:border-ink/10 md:px-3 md:py-6">
        <div className="px-3 pb-6 flex items-center gap-2">
          <span className="font-mono text-xs bg-ink text-accent px-[7px] py-1 rounded tracking-wide">00:00</span>
          <span className="font-display text-lg font-bold tracking-tight">{APP_NAME}</span>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.to} {...item} />
          ))}
        </nav>
        <button
          onClick={logout}
          className="mt-auto text-left px-4 py-2.5 rounded-lg text-sm font-medium text-ink/50 hover:bg-ink/5"
        >
          Log out
        </button>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-ink/10 sticky top-0 bg-paper z-10">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs bg-ink text-accent px-[7px] py-1 rounded tracking-wide">00:00</span>
          <span className="font-display text-lg font-bold tracking-tight">{APP_NAME}</span>
        </div>
        <button onClick={logout} className="text-xs font-medium text-ink/50">
          Log out
        </button>
      </header>

      <main className="flex-1 px-4 py-5 md:px-8 md:py-8 pb-20 md:pb-8 max-w-3xl w-full mx-auto">
        <Outlet />
      </main>

      <NotificationPrompt />

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 flex border-t border-ink/10 bg-paper z-10">
        {NAV_ITEMS.map((item) => (
          <NavLinkItem key={item.to} {...item} mobile />
        ))}
      </nav>
    </div>
  );
}
