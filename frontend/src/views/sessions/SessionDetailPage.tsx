import {
  Box,
  Heading,
  HStack,
  Text,
  Spinner,
  Badge,
  VStack,
  Center,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { useSessionTimeline } from "@/shared/hooks/useApi";
import { SessionTimeline } from "./components/SessionTimeline";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useSessionTimeline(id || "");

  if (!id) return <Text>No session ID</Text>;
  if (isLoading) return <Center h="50vh"><Spinner color="brand.500" size="lg" /></Center>;
  if (error) return <Text color="red.500">Failed to load session</Text>;

  const events = data?.events || [];

  return (
    <Box p={8}>
      <VStack align="stretch" spacing={5}>
        <Box>
          <Heading size="lg" mb={2}>Session Timeline</Heading>
          <HStack spacing={3}>
            <Text fontFamily="mono" fontSize="xs" color="gray.500" bg="surface.muted" px={2} py={1} borderRadius="md">
              {id}
            </Text>
            <Badge colorScheme="blue" variant="subtle">
              {events.length} events
            </Badge>
          </HStack>
        </Box>
        <SessionTimeline events={events} sessionId={id} />
      </VStack>
    </Box>
  );
}
