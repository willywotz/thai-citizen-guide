import { MessageSquare, LayoutDashboard, Building2, History, Network } from "lucide-react";
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
  const collapsed = state === "collapsed";

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
      </SidebarContent>
    </Sidebar>
  );
}
