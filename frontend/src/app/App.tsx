import { ChakraProvider, Spinner, Center, Box, Text, Code } from "@chakra-ui/react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense, Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { QueryProvider } from "./providers/QueryProvider";
import { Layout } from "./Layout";
import { viewRegistry } from "./router/viewRegistry";
import { theme } from "./theme";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null; errorInfo: ErrorInfo | null }
> {
  state = { error: null as Error | null, errorInfo: null as ErrorInfo | null };

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.error) {
      return (
        <Box p={8}>
          <Text fontSize="lg" fontWeight="bold" color="red.500" mb={2}>
            Something went wrong
          </Text>
          <Code display="block" whiteSpace="pre-wrap" p={4} mb={4} colorScheme="red">
            {this.state.error.toString()}
          </Code>
          <Code display="block" whiteSpace="pre-wrap" p={4} fontSize="xs" maxH="300px" overflowY="auto">
            {this.state.errorInfo?.componentStack}
          </Code>
        </Box>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ChakraProvider theme={theme}>
      <QueryProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <Suspense
              fallback={
                <Center h="100vh">
                  <Spinner size="xl" />
                </Center>
              }
            >
              <Routes>
                <Route element={<Layout />}>
                  {viewRegistry.map((v) => (
                    <Route key={v.id} path={v.path} element={<v.component />} />
                  ))}
                  <Route
                    path="/"
                    element={<Navigate to="/dashboard" replace />}
                  />
                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
      </QueryProvider>
    </ChakraProvider>
  );
}
