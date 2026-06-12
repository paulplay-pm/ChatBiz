import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { MENU_ITEMS } from "@/config/menuItems";

describe("AppShell", () => {
  it("renders 14 menu items with correct hrefs", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell />
      </MemoryRouter>,
    );

    // spec `playwright-smoke` § Requirement: Bootstrap unit test exists
    // 验 14 个 menu item 都渲染出对应 href 的链接
    expect(MENU_ITEMS).toHaveLength(14);

    for (const item of MENU_ITEMS) {
      const link = screen.getByRole("link", { name: new RegExp(item.name, "i") });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", item.href);
    }

    // 总数 14 条 nav link（不含 header 里的元素）
    const nav = screen.getByRole("navigation", { name: "主导航" });
    expect(nav).toBeInTheDocument();
    const links = nav.querySelectorAll("a");
    expect(links).toHaveLength(MENU_ITEMS.length);
  });
});
