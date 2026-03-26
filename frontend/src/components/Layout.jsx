import { NavLink, Outlet } from "react-router-dom";
import { Package, Images, LogOut, Zap } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const navItems = [
  { to: "/produtos", icon: Package, label: "Produtos" },
  { to: "/pipeline", icon: Zap, label: "Pipeline" },
];

export default function Layout() {
  const { logout } = useAuth();

  return (
    <div className="flex h-screen bg-surface-950 text-neutral-100 font-body">
      {/* Sidebar */}
      <aside className="w-56 bg-surface-900 border-r border-surface-700 flex flex-col">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-surface-700">
          <span className="font-display text-xl text-amber-400">Confex</span>
          <span className="font-display text-xl text-neutral-100">AI</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all ${
                  isActive
                    ? "bg-amber-500/10 text-amber-400 font-medium"
                    : "text-neutral-400 hover:text-neutral-100 hover:bg-surface-700"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-4 border-t border-surface-700">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2 w-full rounded-md text-sm text-neutral-400 hover:text-red-400 hover:bg-surface-700 transition-all"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
