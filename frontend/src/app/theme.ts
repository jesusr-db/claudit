import { extendTheme, type ThemeConfig } from "@chakra-ui/react";

/* ── Soft UI Evolution Theme for Claudit ──
 *  Evolved neumorphism with improved contrast (WCAG AA+),
 *  subtle depth via multi-layer shadows, modern 200-300ms transitions.
 */

const config: ThemeConfig = {
  initialColorMode: "light",
  useSystemColorMode: false,
};

const colors = {
  brand: {
    50: "#EFF6FF",
    100: "#DBEAFE",
    200: "#BFDBFE",
    300: "#93C5FD",
    400: "#60A5FA",
    500: "#3B82F6",
    600: "#2563EB",
    700: "#1D4ED8",
    800: "#1E40AF",
    900: "#1E3A8A",
  },
  accent: {
    50: "#FFFBEB",
    100: "#FEF3C7",
    200: "#FDE68A",
    300: "#FCD34D",
    400: "#FBBF24",
    500: "#F59E0B",
    600: "#D97706",
    700: "#B45309",
  },
  surface: {
    bg: "#F8FAFC",
    card: "#FFFFFF",
    sidebar: "#FFFFFF",
    elevated: "#FFFFFF",
    muted: "#F1F5F9",
  },
  soft: {
    border: "#E2E8F0",
    divider: "#E2E8F0",
    hover: "#F1F5F9",
    active: "#EFF6FF",
  },
};

const fonts = {
  heading: `'Fira Sans', -apple-system, BlinkMacSystemFont, sans-serif`,
  body: `'Fira Sans', -apple-system, BlinkMacSystemFont, sans-serif`,
  mono: `'Fira Code', 'Menlo', monospace`,
};

const shadows = {
  soft: "0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)",
  "soft-md": "0 4px 16px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04)",
  "soft-lg": "0 8px 24px rgba(0,0,0,0.08), 0 4px 8px rgba(0,0,0,0.04)",
  "soft-hover": "0 6px 20px rgba(0,0,0,0.08), 0 3px 6px rgba(0,0,0,0.05)",
  "soft-inset": "inset 0 2px 4px rgba(0,0,0,0.04)",
};

const radii = {
  soft: "10px",
  "soft-lg": "14px",
  "soft-xl": "18px",
};

const styles = {
  global: {
    "html, body": {
      bg: "surface.bg",
      color: "gray.800",
      fontFamily: "body",
      lineHeight: 1.6,
    },
    "*::selection": {
      bg: "brand.100",
      color: "brand.900",
    },
  },
};

const components = {
  Card: {
    baseStyle: {
      container: {
        bg: "surface.card",
        borderRadius: "soft",
        boxShadow: "soft",
        border: "1px solid",
        borderColor: "soft.border",
        transition: "all 0.2s ease",
        _hover: {
          boxShadow: "soft-hover",
        },
      },
    },
    variants: {
      soft: {
        container: {
          bg: "surface.card",
          boxShadow: "soft",
          borderColor: "soft.border",
        },
      },
      elevated: {
        container: {
          bg: "surface.elevated",
          boxShadow: "soft-md",
          borderColor: "transparent",
        },
      },
    },
    defaultProps: {
      variant: "soft",
    },
  },
  Button: {
    baseStyle: {
      borderRadius: "soft",
      fontWeight: 500,
      transition: "all 0.2s ease",
    },
    variants: {
      solid: {
        bg: "brand.500",
        color: "white",
        boxShadow: "soft",
        _hover: {
          bg: "brand.600",
          boxShadow: "soft-md",
          transform: "translateY(-1px)",
        },
        _active: {
          bg: "brand.700",
          transform: "translateY(0)",
          boxShadow: "soft-inset",
        },
      },
      softOutline: {
        bg: "surface.card",
        color: "brand.600",
        border: "1px solid",
        borderColor: "brand.200",
        boxShadow: "soft",
        _hover: {
          bg: "brand.50",
          borderColor: "brand.300",
          boxShadow: "soft-md",
        },
        _active: {
          bg: "brand.100",
        },
      },
      ghost: {
        _hover: {
          bg: "soft.hover",
        },
      },
    },
  },
  Table: {
    variants: {
      soft: {
        table: {
          borderRadius: "soft",
          overflow: "hidden",
        },
        thead: {
          bg: "surface.muted",
          th: {
            color: "gray.600",
            fontWeight: 600,
            fontSize: "xs",
            textTransform: "uppercase",
            letterSpacing: "wider",
            borderColor: "soft.border",
          },
        },
        tbody: {
          tr: {
            _hover: {
              bg: "soft.hover",
            },
            td: {
              borderColor: "soft.border",
            },
          },
        },
      },
    },
    defaultProps: {
      variant: "soft",
    },
  },
  Badge: {
    baseStyle: {
      borderRadius: "full",
      px: 2,
      py: 0.5,
      fontWeight: 500,
      fontSize: "xs",
    },
  },
  Tabs: {
    variants: {
      "soft-rounded": {
        tablist: {
          bg: "surface.muted",
          borderRadius: "soft",
          p: 1,
        },
        tab: {
          borderRadius: "8px",
          fontWeight: 500,
          color: "gray.600",
          _selected: {
            bg: "surface.card",
            color: "brand.700",
            boxShadow: "soft",
          },
          _hover: {
            color: "brand.600",
          },
        },
      },
    },
  },
  Heading: {
    baseStyle: {
      color: "gray.800",
      fontWeight: 600,
    },
  },
  Stat: {
    baseStyle: {
      label: {
        color: "gray.500",
        fontWeight: 500,
        fontSize: "xs",
        textTransform: "uppercase",
        letterSpacing: "wider",
      },
      number: {
        color: "gray.800",
        fontWeight: 600,
      },
    },
  },
  Tooltip: {
    baseStyle: {
      borderRadius: "8px",
      boxShadow: "soft-md",
      bg: "gray.800",
      color: "white",
      px: 3,
      py: 2,
      fontSize: "xs",
    },
  },
};

export const theme = extendTheme({
  config,
  colors,
  fonts,
  shadows,
  radii,
  styles,
  components,
});
