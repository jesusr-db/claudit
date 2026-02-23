import { ChakraProvider } from "@chakra-ui/react";
import { BrowserRouter } from "react-router-dom";
import { QueryProvider } from "./providers/QueryProvider";

export default function App() {
  return (
    <ChakraProvider>
      <QueryProvider>
        <BrowserRouter>
          <div>Claudit app shell</div>
        </BrowserRouter>
      </QueryProvider>
    </ChakraProvider>
  );
}
