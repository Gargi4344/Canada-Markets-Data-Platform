import {
  Activity,
  BookOpen,
  LayoutDashboard,
  Landmark,
  LineChart,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const site = {
  name: "Canada Markets Data Platform",
  short: "CMDP",
  tagline: "Bank of Canada and Statistics Canada market data, tested and documented.",
  repo: "https://github.com/Gargi4344/canada-markets-data-platform",
  nav: [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/yield-curve", label: "Yield Curve", icon: LineChart },
    { href: "/fx", label: "FX", icon: Activity },
    { href: "/policy", label: "Policy & Inflation", icon: Landmark },
    { href: "/data-quality", label: "Data Quality", icon: ShieldCheck },
    { href: "/catalog", label: "Data Catalog", icon: BookOpen },
  ] satisfies NavItem[],
  sources: [
    {
      name: "Bank of Canada Valet API",
      url: "https://www.bankofcanada.ca/valet/docs",
      detail:
        "Target for the overnight rate, CORRA, Government of Canada benchmark bond yields and daily exchange rates.",
      licence: "Bank of Canada terms of use",
      licenceUrl: "https://www.bankofcanada.ca/terms/",
    },
    {
      name: "Statistics Canada, table 18-10-0004-01",
      url: "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401",
      detail: "Consumer Price Index, monthly, not seasonally adjusted (all-items, food, shelter, energy).",
      licence: "Open Government Licence – Canada",
      licenceUrl: "https://open.canada.ca/en/open-government-licence-canada",
    },
  ],
};
