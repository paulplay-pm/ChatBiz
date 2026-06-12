interface PlaceholderViewProps {
  readonly menuItemName: string;
  readonly changeName: string;
}

/**
 * 未实现路由的占位卡片 — spec `placeholder-view`。
 * 后续 change 落地真实视图时替换 router/index.tsx 里对应 path 的 element。
 */
export function PlaceholderView({ menuItemName, changeName }: PlaceholderViewProps): JSX.Element {
  return (
    <div className="max-w-md mx-auto mt-24 bg-white rounded-xl border border-dashed border-ink-300 p-12 text-center">
      <i
        className="fas fa-plus text-2xl text-ink-400 mb-4 block"
        aria-hidden="true"
      />
      <h2 className="text-xl font-semibold text-ink-800 mb-2">
        🚧 {menuItemName} 即将推出
      </h2>
      <p className="text-sm text-ink-500">由后续 change {changeName} 落地</p>
    </div>
  );
}
