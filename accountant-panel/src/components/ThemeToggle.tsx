import { Button, Dropdown, Tooltip } from "antd";
import { Laptop, Moon, Sun } from "lucide-react";
import { useTheme, type ThemeMode } from "../theme/ThemeProvider";

export function ThemeToggle() {
  const { mode, setMode } = useTheme();
  return (
    <Tooltip title={`Theme: ${mode}`}>
      <Dropdown
        trigger={["click"]}
        menu={{
          selectedKeys: [mode],
          onClick: ({ key }) => setMode(key as ThemeMode),
          items: [
            { key: "light", label: "Light", icon: <Sun /> },
            { key: "dark", label: "Dark", icon: <Moon /> },
            { key: "system", label: "System", icon: <Laptop /> },
          ],
        }}
      >
        <Button
          type="text"
          aria-label={`Choose theme, current ${mode}`}
          icon={
            mode === "dark" ? (
              <Moon />
            ) : mode === "system" ? (
              <Laptop />
            ) : (
              <Sun />
            )
          }
        />
      </Dropdown>
    </Tooltip>
  );
}
