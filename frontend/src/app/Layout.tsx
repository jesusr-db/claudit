import {
  Box,
  Flex,
  VStack,
  Link as ChakraLink,
  Heading,
  Divider,
} from "@chakra-ui/react";
import { Link, useLocation, Outlet } from "react-router-dom";
import { viewRegistry } from "./router/viewRegistry";

export function Layout() {
  const location = useLocation();

  const navItems = viewRegistry.filter((v) => v.nav);

  return (
    <Flex minH="100vh">
      <Box w="220px" bg="gray.50" p={4} borderRight="1px" borderColor="gray.200">
        <Heading size="md" mb={4}>
          Claudit
        </Heading>
        <Divider mb={4} />
        <VStack align="stretch" spacing={1}>
          {navItems.map((v) => (
            <ChakraLink
              as={Link}
              to={v.path}
              key={v.id}
              px={3}
              py={2}
              borderRadius="md"
              bg={location.pathname.startsWith(v.path) ? "blue.50" : "transparent"}
              color={location.pathname.startsWith(v.path) ? "blue.600" : "gray.700"}
              fontWeight={location.pathname.startsWith(v.path) ? "semibold" : "normal"}
              _hover={{ bg: "blue.50" }}
            >
              {v.label}
            </ChakraLink>
          ))}
        </VStack>
      </Box>
      <Box flex={1} overflow="auto">
        <Outlet />
      </Box>
    </Flex>
  );
}
