import { ChakraProvider, Spinner, Center } from "@chakra-ui/react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense } from "react";
import { QueryProvider } from "./providers/QueryProvider";
import { Layout } from "./Layout";
import { viewRegistry } from "./router/viewRegistry";

export default function App() {
  return (
    <ChakraProvider>
      <QueryProvider>
        <BrowserRouter>
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
        </BrowserRouter>
      </QueryProvider>
    </ChakraProvider>
  );
}
