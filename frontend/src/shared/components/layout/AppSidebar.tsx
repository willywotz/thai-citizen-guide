import { MessageSquare, LayoutDashboard, Building2, History, Network, LogOut, Activity, KeyRound, Briefcase, Flame, Settings, Users, MessageSquareWarning, BadgeCheck, ScrollText } from "lucide-react";
import { NavLink } from "@/shared/components/NavLink";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/shared/components/ui/sidebar";
import { useAgencies } from "@/features/agencies/useAgencies";
import { useAuth } from "@/features/auth/useAuth";
import { Button } from "@/shared/components/ui/button";
import { Avatar, AvatarFallback } from "@/shared/components/ui/avatar";
import { AppLogo } from "@/shared/components/ui/AppLogo";

const navItems = [
  { title: "แชท", url: "/chat", icon: MessageSquare },
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Executive", url: "/executive", icon: Briefcase },
  { title: "Agency Health", url: "/health", icon: Activity },
  { title: "Usage Heatmap", url: "/heatmap", icon: Flame },
  { title: "จัดการหน่วยงาน", url: "/agencies", icon: Building2 },
  { title: "ประวัติการสนทนา", url: "/history", icon: History },
  { title: "ประวัติการเชื่อมต่อ", url: "/connection-logs", icon: Activity },
  { title: "Architecture", url: "/architecture", icon: Network },
  { title: "API Keys", url: "/api-keys", icon: KeyRound },
];

const ownerItems = [
  { title: "หน่วยงานของฉัน", url: "/my-agencies", icon: BadgeCheck },
];

const adminItems = [
  { title: "ความคิดเห็นและความพึงพอใจ", url: "/feedback", icon: MessageSquareWarning },
  { title: "จัดการผู้ใช้", url: "/users", icon: Users },
  { title: "บันทึกการตรวจสอบ", url: "/audit-log", icon: ScrollText },
  { title: "ตั้งค่าระบบ", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const { data: agencies = [] } = useAgencies();
  const { user, signOut } = useAuth();
  const collapsed = state === "collapsed";

  const initials = (user?.displayName || user?.email || "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarContent>
        {/* Logo area */}
        <div className="p-4 border-b border-sidebar-border">
          {!collapsed ? (
            <div className="flex items-center gap-2">
              <AppLogo className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm" />
              <div>
                <p className="font-semibold text-sm text-sidebar-foreground">AI Portal กลาง</p>
                <p className="text-[10px] text-muted-foreground">ระบบบูรณาการข้อมูล</p>
              </div>
            </div>
          ) : (
            <AppLogo className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm" />
          )}
        </div>

        {/* Navigation */}
        <SidebarGroup>
          <SidebarGroupLabel>เมนูหลัก</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink
                      to={item.url}
                      end={item.url === "/chat"}
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                      activeClassName="bg-sidebar-accent text-sidebar-primary font-medium"
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              {(user?.role === "agency_owner" || user?.role === "admin") && ownerItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink
                      to={item.url}
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                      activeClassName="bg-sidebar-accent text-sidebar-primary font-medium"
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              {user?.role === "admin" && adminItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink
                      to={item.url}
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                      activeClassName="bg-sidebar-accent text-sidebar-primary font-medium"
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Connected agencies */}
        {!collapsed && (
          <SidebarGroup>
            <SidebarGroupLabel>หน่วยงานที่เชื่อมต่อ</SidebarGroupLabel>
            <SidebarGroupContent>
              <div className="px-3 space-y-2">
                {agencies.map((agency) => (
                  <div key={agency.id} className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                    <span className="text-sidebar-foreground truncate">{agency.shortName}</span>
                  </div>
                ))}
              </div>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {/* User section at bottom */}
        <div className="mt-auto border-t border-sidebar-border p-3">
          {!collapsed ? (
            <div className="flex items-center gap-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="text-xs bg-primary text-primary-foreground">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-sidebar-foreground truncate">
                  {user?.displayName || user?.email}
                </p>
                <p className="text-[10px] text-muted-foreground truncate">{user?.email}</p>
              </div>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={signOut} title="ออกจากระบบ">
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : (
            <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto" onClick={signOut} title="ออกจากระบบ">
              <LogOut className="h-4 w-4" />
            </Button>
          )}
        </div>
      </SidebarContent>
    </Sidebar>
  );
}
