import {
  Box,
  Flex,
  VStack,
  HStack,
  Link as ChakraLink,
  Text,
  Icon,
} from "@chakra-ui/react";
import { Link, useLocation, Outlet } from "react-router-dom";
import { viewRegistry } from "./router/viewRegistry";
import TimeRangeSelector from "@/shared/components/TimeRangeSelector";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import {
  FiGrid,
  FiMessageSquare,
  FiCpu,
  FiBarChart2,
  FiServer,
  FiTrendingUp,
  FiSearch,
} from "react-icons/fi";

const NAV_ICONS: Record<string, React.ElementType> = {
  "mcp-servers": FiServer,
  dashboard: FiGrid,
  sessions: FiMessageSquare,
  "mcp-tools": FiCpu,
  kpis: FiTrendingUp,
  platform: FiBarChart2,
  introspection: FiSearch,
};

export function Layout() {
  const location = useLocation();
  const { days, setDays } = useTimeRange();
  const navItems = viewRegistry.filter((v) => v.nav);

  return (
    <Flex minH="100vh" bg="surface.bg">
      {/* Soft UI Sidebar */}
      <Box
        w="240px"
        bg="surface.sidebar"
        borderRight="1px solid"
        borderColor="soft.border"
        boxShadow="2px 0 12px rgba(0,0,0,0.03)"
        py={6}
        px={4}
        position="sticky"
        top={0}
        h="100vh"
        display="flex"
        flexDirection="column"
      >
        {/* Brand */}
        <HStack spacing={2} px={3} mb={8}>
          <Box
            w="32px"
            h="32px"
            borderRadius="soft"
            bg="brand.500"
            display="flex"
            alignItems="center"
            justifyContent="center"
            boxShadow="soft"
          >
            <Text color="white" fontWeight="bold" fontSize="sm">
              C
            </Text>
          </Box>
          <Box>
            <Text fontWeight="700" fontSize="md" color="gray.800" lineHeight="1.2">
              Claudit
            </Text>
            <Text fontSize="10px" color="gray.400" fontWeight="500" letterSpacing="wider" textTransform="uppercase">
              Observability
            </Text>
          </Box>
        </HStack>

        {/* Navigation */}
        <VStack align="stretch" spacing={1} flex={1}>
          {navItems.map((v) => {
            const isActive = location.pathname.startsWith(v.path);
            const NavIcon = NAV_ICONS[v.id] || FiGrid;
            return (
              <ChakraLink
                as={Link}
                to={v.path}
                key={v.id}
                px={3}
                py={2.5}
                borderRadius="soft"
                bg={isActive ? "soft.active" : "transparent"}
                color={isActive ? "brand.700" : "gray.600"}
                fontWeight={isActive ? "600" : "500"}
                fontSize="sm"
                display="flex"
                alignItems="center"
                gap={3}
                transition="all 0.2s ease"
                _hover={{
                  bg: isActive ? "soft.active" : "soft.hover",
                  color: isActive ? "brand.700" : "gray.800",
                  textDecoration: "none",
                  transform: "translateX(2px)",
                }}
                position="relative"
                _before={
                  isActive
                    ? {
                        content: '""',
                        position: "absolute",
                        left: "-4px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        w: "3px",
                        h: "20px",
                        bg: "brand.500",
                        borderRadius: "full",
                      }
                    : undefined
                }
              >
                <Icon as={NavIcon} boxSize={4} />
                {v.label}
              </ChakraLink>
            );
          })}
        </VStack>

        {/* Global Time Range */}
        <Box px={3} py={3} borderTop="1px solid" borderColor="soft.border">
          <Text fontSize="10px" color="gray.400" fontWeight="500" mb={2} textTransform="uppercase" letterSpacing="wider">
            Time Range
          </Text>
          <TimeRangeSelector value={days} onChange={setDays} />
        </Box>

        {/* Footer */}
        <Box px={3} pt={3} borderTop="1px solid" borderColor="soft.border">
          <Text fontSize="10px" color="gray.400">
            Claude Code Observability
          </Text>
        </Box>
      </Box>

      {/* Main Content */}
      <Box flex={1} overflow="auto" minH="100vh">
        <Outlet />
      </Box>
    </Flex>
  );
}
