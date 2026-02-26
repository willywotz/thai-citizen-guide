import { MessageSquare, LayoutDashboard, Building2, History, Network, LogOut } from "lucide-react";
import { NavLink } from "@/components/NavLink";
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
} from "@/components/ui/sidebar";
import { useAgencies } from "@/hooks/useAgencies";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const navItems = [
  { title: "แชท", url: "/", icon: MessageSquare },
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "จัดการหน่วยงาน", url: "/agencies", icon: Building2 },
  { title: "ประวัติการสนทนา", url: "/history", icon: History },
  { title: "Architecture", url: "/architecture", icon: Network },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const { data: agencies = [] } = useAgencies();
  const { profile, user, signOut } = useAuth();
  const collapsed = state === "collapsed";

  const initials = (profile?.displayName || user?.email || "U")
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
              <div className="w-8 h-8 rounded-lg gov-gradient flex items-center justify-center text-white font-bold text-sm">
                AI
              </div>
              <div>
                <p className="font-semibold text-sm text-sidebar-foreground">AI Portal กลาง</p>
                <p className="text-[10px] text-muted-foreground">ระบบบูรณาการข้อมูล</p>
              </div>
            </div>
          ) : (
            <div className="w-8 h-8 rounded-lg gov-gradient flex items-center justify-center text-white font-bold text-sm mx-auto">
              AI
            </div>
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
                      end={item.url === "/"}
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
                  {profile?.displayName || user?.email}
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
