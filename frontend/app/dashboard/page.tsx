/**
 * Route "/dashboard" — a dedicated page for the dashboard.
 *
 * Exists so you can deep-link to the dashboard. It simply renders the Dashboard
 * component (which does its own data fetching).
 */
import Dashboard from "@/components/Dashboard";

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-4xl p-4">
      {/* TODO: optional page heading / breadcrumb */}
      <Dashboard />
    </main>
  );
}
